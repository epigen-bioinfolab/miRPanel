"""HTTP API over the orchestrator. Read-only, except for creating jobs."""
import json
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

import db
import orchestrator
import resolve
from tools import registry

app = FastAPI(title="miRNA target tool", version="0.1")


def get_con():
    """One SQLite connection per request, closed when the request ends."""
    con = db.connect()
    try:
        yield con
    finally:
        con.close()


@app.get("/health")
def health():
    """Proves the server is up. Touches nothing else."""
    return {"status": "ok"}


@app.get("/tools")
def list_tools():
    """Every tool the orchestrator can run, with the metadata a frontend
    needs to build its columns and sort them the right way round."""
    metas = [m.META for m in registry.load().values()]
    metas.sort(key=lambda meta: meta["name"])
    return {"tools": metas}


class JobRequest(BaseModel):
    """What a client sends to start a job."""
    mirna: str = Field(..., min_length=2, description="name or MIMAT accession")
    tools: Optional[List[str]] = None
    genes: Optional[List[str]] = None
    batch_id: Optional[str] = None


@app.post("/jobs", status_code=202)
def post_job(req: JobRequest, con=Depends(get_con)):
    """Queue one miRNA. The worker runs it; poll GET /jobs/{job_id}."""
    m = resolve.resolve_mirna(con, req.mirna)
    if not m:
        raise HTTPException(404, {"error": "mirna_not_found", "query": req.mirna})
    if "accession" not in m:
        raise HTTPException(409, {"error": "mirna_ambiguous", "query": req.mirna,
                                  "candidates": m.get("candidates", [])})
    try:
        job_id = orchestrator.create_job(con, req.mirna, tools=req.tools,
                                         genes=req.genes, batch_id=req.batch_id)
    except ValueError as e:
        raise HTTPException(422, {"error": "bad_request", "message": str(e)})
    return orchestrator.job_status(con, job_id)


@app.get("/jobs/{job_id}")
def read_job(job_id: str, con=Depends(get_con)):
    """Status, timings and the per-tool record of one job."""
    st = orchestrator.job_status(con, job_id)
    if st is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    return st


RESULT_COLS = ("mirna_acc", "mirna_name", "entrez", "symbol", "refseq",
               "region", "tool", "site_type", "pos_start", "pos_end",
               "score", "score_type", "low_confidence", "extra")


def _where(job_id, tool, region, site_type, gene):
    """Build the WHERE clause from whatever filters were supplied."""
    parts, args = ["job_id = ?"], [job_id]
    for col, val in (("tool", tool), ("region", region), ("site_type", site_type)):
        if val:
            parts.append(col + " = ?")
            args.append(val)
    if gene:
        parts.append("(symbol = ? COLLATE NOCASE OR entrez = ?)")
        args += [gene, gene]
    return " AND ".join(parts), args


def _order(sort, tool):
    """Sorting never guesses a direction: it reads it from the tool's META."""
    if sort == "gene":
        return "symbol, tool, pos_start", []
    if sort == "position":
        return "pos_start IS NULL, pos_start, tool", []
    metas = {m.META["name"]: m.META for m in registry.load().values()}
    if tool not in metas:
        raise HTTPException(422, {"error": "sort_needs_tool", "sort": sort,
            "message": "sort=%s compares one tool's own scale, so ?tool= is "
                       "required" % sort})
    meta = metas[tool]
    if sort == "score":
        if meta["better"] is None:
            raise HTTPException(422, {"error": "score_not_numeric", "tool": tool,
                "message": "%s reports a category, not a number; use "
                           "sort=site_type" % tool})
        return "score IS NULL, score " + ("ASC" if meta["better"] == "lower"
                                          else "DESC"), []
    cats = meta.get("categories")
    if not cats:
        raise HTTPException(422, {"error": "no_categories", "tool": tool,
            "message": "%s publishes no site categories" % tool})
    case = " ".join("WHEN ? THEN %d" % i for i in range(len(cats)))
    return "CASE site_type " + case + " ELSE 99 END, symbol, pos_start", list(cats)


@app.get("/jobs/{job_id}/results")
def read_results(job_id: str,
                 tool: Optional[str] = None,
                 region: Optional[str] = None,
                 site_type: Optional[str] = None,
                 gene: Optional[str] = None,
                 sort: str = Query("gene", pattern="^(gene|position|score|site_type)$"),
                 limit: int = Query(100, ge=1, le=1000),
                 offset: int = Query(0, ge=0),
                 con=Depends(get_con)):
    """One page of a job's results. Scores are never compared across tools."""
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    where, args = _where(job_id, tool, region, site_type, gene)
    order, oargs = _order(sort, tool)
    total = con.execute("SELECT COUNT(*) FROM results WHERE " + where,
                        args).fetchone()[0]
    rows = con.execute("SELECT " + ", ".join(RESULT_COLS) + " FROM results WHERE "
                       + where + " ORDER BY " + order + " LIMIT ? OFFSET ?",
                       args + oargs + [limit, offset]).fetchall()
    out = []
    for r in rows:
        d = dict(zip(RESULT_COLS, r))
        d["extra"] = json.loads(d["extra"]) if d["extra"] else None
        out.append(d)
    return {"job_id": job_id, "total": total, "limit": limit,
            "offset": offset, "sort": sort, "results": out}
