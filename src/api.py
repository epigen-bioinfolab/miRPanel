"""HTTP API over the orchestrator. Read-only, except for creating jobs."""
import json
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import db
import geneset
import orchestrator
import resolve
import targets as T
from tools import registry

app = FastAPI(title=config.TOOL_NAME, version=config.TOOL_VERSION)


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
    genes = {t: n for t, n in con.execute(
        "SELECT tool, COUNT(DISTINCT entrez) FROM results WHERE job_id=? "
        "GROUP BY tool", (job_id,))}
    for t in st["tools"]:
        t["n_genes"] = genes.get(t["tool"])
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


@app.get("/about")
def about(con=Depends(get_con)):
    """Who this tool is, and which release of every source produced the
    numbers. The frontend renders its title and its provenance line from
    here, so neither is hard-coded in the page."""
    rows = con.execute("SELECT name, version, url, downloaded_on, notes "
                       "FROM data_sources ORDER BY name").fetchall()
    return {"name": config.TOOL_NAME, "version": config.TOOL_VERSION,
            "description": config.TOOL_DESCRIPTION,
            "subtitle": config.TOOL_SUBTITLE,
            "data_sources": [{"name": r[0], "version": r[1], "url": r[2],
                              "downloaded_on": r[3], "notes": r[4]}
                             for r in rows]}


@app.get("/genes/{gene}")
def read_gene(gene: str, con=Depends(get_con)):
    """The MANE Select transcript for one gene: its length and its region
    boundaries. The binding map draws itself from this."""
    g = resolve.resolve_gene(con, gene)
    if not g or "entrez" not in g:
        raise HTTPException(404, {"error": "gene_not_found", "query": gene})
    hits = T.targets_for(con, [g["entrez"]])
    if not hits:
        raise HTTPException(404, {"error": "no_mane_transcript", "query": gene,
                                  "entrez": g["entrez"]})
    t = hits[0]
    regs = T.regions(con, [t["refseq"]]).get(t["refseq"], [])
    return {"entrez": t["entrez"], "symbol": t["symbol"], "refseq": t["refseq"],
            "length": t["length"],
            "regions": [{"region": r, "start": a, "end": b}
                        for r, a, b in sorted(regs, key=lambda x: x[1])]}


@app.get("/mirnas/{query}")
def read_mirna(query: str, con=Depends(get_con)):
    """Resolve one miRNA and return what the query panel shows: accession,
    mature sequence, seed, and its TargetScan family if it has one."""
    m = resolve.resolve_mirna(con, query)
    if not m:
        raise HTTPException(404, {"error": "mirna_not_found", "query": query})
    if "accession" not in m:
        raise HTTPException(409, {"error": "mirna_ambiguous", "query": query,
                                  "candidates": m.get("candidates", [])})
    ts = con.execute("SELECT family, conservation, seed FROM targetscan_mirnas "
                     "WHERE accession=?", (m["accession"],)).fetchone()
    out = dict(m)
    out["targetscan"] = None if ts is None else {
        "family": ts[0], "conservation": ts[1], "seed": ts[2],
        "seed_matches_mirbase": ts[2] == m["seed"]}
    return out


def _gene_order(sort):
    """How to rank genes. Direction always comes from the tool's META."""
    metas = {m.META["name"]: m.META for m in registry.load().values()}
    if sort == "gene":
        return "symbol", []
    if sort == "seed":
        cats = metas["seed"]["categories"]
        case = " ".join("WHEN ? THEN %d" % (len(cats) - i)
                        for i in range(len(cats)))
        return ("MAX(CASE WHEN tool='seed' THEN (CASE site_type " + case +
                " ELSE 0 END) END) DESC, symbol"), list(cats)
    meta = metas.get(sort)
    if meta is None or meta["better"] is None:
        raise HTTPException(422, {"error": "bad_sort", "sort": sort,
            "message": "sort must be 'gene', 'seed', or a tool with a "
                       "numeric score"})
    agg = "MIN" if meta["better"] == "lower" else "MAX"
    expr = "%s(CASE WHEN tool=? THEN score END)" % agg
    direction = "ASC" if meta["better"] == "lower" else "DESC"
    return "%s IS NULL, %s %s, symbol" % (expr, expr, direction), [sort, sort]


@app.get("/jobs/{job_id}/genes")
def read_genes(job_id: str,
               sort: str = Query("gene", pattern="^[a-z_]+$"),
               limit: int = Query(25, ge=1, le=200),
               offset: int = Query(0, ge=0),
               con=Depends(get_con)):
    """One page of genes, with every record for those genes and the
    transcript geometry the binding map needs. The table is gene-level, so
    the API pages by gene rather than by row."""
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    order, oargs = _gene_order(sort)
    total = con.execute("SELECT COUNT(DISTINCT symbol) FROM results "
                        "WHERE job_id=?", (job_id,)).fetchone()[0]
    syms = [r[0] for r in con.execute(
        "SELECT symbol FROM results WHERE job_id=? GROUP BY symbol "
        "ORDER BY " + order + " LIMIT ? OFFSET ?",
        [job_id] + oargs + [limit, offset])]
    if not syms:
        return {"job_id": job_id, "total_genes": total, "limit": limit,
                "offset": offset, "sort": sort, "genes": [], "results": []}
    qs = ",".join("?" * len(syms))
    rows = con.execute("SELECT " + ", ".join(RESULT_COLS) + " FROM results "
                       "WHERE job_id=? AND symbol IN (" + qs + ") "
                       "ORDER BY symbol, tool, pos_start",
                       [job_id] + syms).fetchall()
    out = []
    for r in rows:
        d = dict(zip(RESULT_COLS, r))
        d["extra"] = json.loads(d["extra"]) if d["extra"] else None
        out.append(d)
    geom = con.execute("SELECT entrez, symbol, refseq, length FROM transcripts "
                       "WHERE symbol IN (" + qs + ") AND mane_status='MANE Select'",
                       syms).fetchall()
    regs = T.regions(con, [g[2] for g in geom])
    order_index = {s: i for i, s in enumerate(syms)}
    genes = [{"entrez": g[0], "symbol": g[1], "refseq": g[2], "length": g[3],
              "regions": [{"region": x[0], "start": x[1], "end": x[2]}
                          for x in sorted(regs.get(g[2], []), key=lambda z: z[1])]}
             for g in geom]
    genes.sort(key=lambda g: order_index.get(g["symbol"], 1e9))
    return {"job_id": job_id, "total_genes": total, "limit": limit,
            "offset": offset, "sort": sort, "genes": genes, "results": out}


@app.get("/jobs/{job_id}/geneset")
def read_geneset(job_id: str,
                 seed: Optional[str] = None,
                 targetscan: Optional[str] = None,
                 rnahybrid: Optional[str] = None,
                 mirtarbase: Optional[str] = None,
                 regions: Optional[str] = None,
                 match: str = Query("all", pattern="^(all|any)$"),
                 include_genes: bool = False,
                 con=Depends(get_con)):
    """How many genes the pathway-analysis tick boxes select, and the rule
    in words. Cheap enough to call on every keystroke, so the count in the
    panel can update live before anything is actually run."""
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    spec = {"seed": seed, "targetscan": targetscan, "rnahybrid": rnahybrid,
            "mirtarbase": mirtarbase, "match": match,
            "regions": regions.split(",") if regions else None}
    try:
        out = geneset.select(con, job_id, spec)
    except ValueError as e:
        raise HTTPException(422, {"error": "bad_filter", "message": str(e)})
    if not include_genes:
        out.pop("genes")
    return out


# Mounted last: it claims "/", so every real endpoint must be declared above.
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
