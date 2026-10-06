"""HTTP API over the orchestrator. Read-only, except for creating jobs."""
import json
import os
from typing import List, Optional

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Query,
                     UploadFile)
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import db
import enrichment
import flatten
import geneset
import agreement
import network
import orchestrator
import provenance
import ranking
import report as R
import resolve
import species as sp
import targets as T
import uploads as U
import xlsx_export
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


def _check_species(con, key):
    """422 unless this species can actually be searched right now.

    For an upload this also touches last_used_at, so an organism
    somebody is actively working with is not swept out from under
    them mid-session."""
    if sp.is_upload(key):
        up = U.get(con, key[len(sp.UPLOAD_PREFIX):])
        if up is None:
            raise HTTPException(404, {"error": "upload_not_found",
                                      "species": key,
                                      "message": "That uploaded organism "
                                      "no longer exists. Uploads are "
                                      "removed after %d hours of disuse."
                                      % U.SWEEP_HOURS})
        if up["status"] != "ready":
            raise HTTPException(409, {"error": "upload_not_ready",
                                      "species": key,
                                      "status": up["status"],
                                      "message": up["error"] or
                                      "That upload is still being read."})
        U.touch(con, key)
        return
    try:
        sp.get(key)
    except ValueError as e:
        raise HTTPException(422, {"error": "unknown_species",
                                  "query": key, "message": str(e)})


@app.post("/uploads", status_code=202)
# A plain def, not async: every other route here is sync, and
# FastAPI runs those in a threadpool. An async route runs on the
# event loop instead, where the SQLite connection that get_con
# built in a worker thread cannot legally be used - SQLite binds a
# connection to its creating thread. UploadFile.file is a plain
# file object, so nothing here actually needs awaiting.
def post_upload(label: str = Form(...),
                      fasta: UploadFile = File(...),
                      gtf: UploadFile = File(...),
                      latin: str = Form(""),
                      con=Depends(get_con)):
    """Accept an organism the user supplies themselves.

    Both files are required. A cDNA FASTA alone carries no CDS
    boundary, and without one every transcript would be treated as
    pure 3'UTR and the region filters would have nothing to filter
    on - so a FASTA-only upload would silently produce worse answers
    rather than obviously failing.

    Parsing takes tens of seconds, so this queues and returns an id
    to poll, like every other slow thing in this tool."""
    # The scientific name is optional and only used to find an
    # annotation database for enrichment. Without it the files still
    # load and prediction still works.
    upload_id = U.create_streamed(con, label,
                                  fasta.filename, fasta.file,
                                  gtf.filename, gtf.file, latin)
    return U.get(con, upload_id)


@app.get("/uploads")
def list_uploads(con=Depends(get_con)):
    """Every upload, newest first - the ready ones and the rest."""
    rows = [r[0] for r in con.execute(
        "SELECT upload_id FROM uploads ORDER BY created_at DESC")]
    return {"uploads": [U.get(con, r) for r in rows],
            "sweep_hours": U.SWEEP_HOURS}


@app.get("/uploads/{upload_id}")
def read_upload(upload_id: str, con=Depends(get_con)):
    """Status of one upload. Polled while it is being read."""
    up = U.get(con, upload_id)
    if up is None:
        raise HTTPException(404, {"error": "upload_not_found",
                                  "upload_id": upload_id})
    return up


@app.delete("/uploads/{upload_id}", status_code=204)
def delete_upload(upload_id: str, con=Depends(get_con)):
    """Remove an upload now rather than waiting for the sweep."""
    if U.get(con, upload_id) is None:
        raise HTTPException(404, {"error": "upload_not_found",
                                  "upload_id": upload_id})
    U.delete(con, upload_id)


@app.get("/species")
def list_species(con=Depends(get_con)):
    """Every organism this installation can analyse.

    The dropdown builds itself from this, so the list of organisms
    exists in exactly one place (src/species.py) rather than being
    repeated in the page. `loaded` is read from the database, not
    declared, so an organism whose transcripts were never loaded
    cannot be offered as if it were ready.

    `tools_unavailable` carries the reason per tool, so the page can
    grey a column and say why instead of showing an empty one.
    """
    loaded = T.counts(con)
    every = sorted(registry.load())
    out = []
    for key in sp.SPECIES:
        rec = sp.get(key)
        out.append({
            "key": key,
            "common": rec["common"],
            "latin": rec["latin"],
            "assembly": rec["assembly"],
            "source": rec["source"],
            "mirbase": rec["mirbase"],
            "transcripts": loaded.get(key, 0),
            "loaded": loaded.get(key, 0) > 0,
            "fasta_url": None if key in sp.PRELOADED else sp.fasta_url(key),
            "gtf_url": None if key in sp.PRELOADED else sp.gtf_url(key),
            "files": None if key in sp.PRELOADED else list(sp.files(key)),
            "tools": [t for t in every if sp.supports(key, t)],
            "tools_unavailable": [
                {"tool": t, "reason": sp.unsupported_reason(key, t)}
                for t in every if not sp.supports(key, t)],
        })
    # Ready uploads are listed as organisms in their own right, so
    # the picker needs no separate concept of them. They carry the
    # user's own label and the two tools that can run on an organism
    # nobody built datasets for.
    for up in U.ready(con):
        key = up["species"]
        rec = sp.get(key, up["label"])
        out.append({
            "key": key,
            "common": up["label"],
            "latin": "",
            "assembly": rec["assembly"],
            "source": "Upload",
            "mirbase": "",
            "transcripts": up["n_transcripts"] or 0,
            "loaded": True,
            "upload_id": up["upload_id"],
            "uploaded_at": up["finished_at"],
            "fasta_url": None, "gtf_url": None, "files": None,
            "tools": [t for t in every if sp.supports(key, t)],
            "tools_unavailable": [
                {"tool": t, "reason": sp.unsupported_reason(key, t)}
                for t in every if not sp.supports(key, t)],
        })
    return {"default": sp.DEFAULT, "species": out,
            "upload_sweep_hours": U.SWEEP_HOURS}


class JobRequest(BaseModel):
    """What a client sends to start a job."""
    mirna: str = Field(..., min_length=2, description="name or MIMAT accession")
    tools: Optional[List[str]] = None
    genes: Optional[List[str]] = None
    batch_id: Optional[str] = None
    species: str = Field(sp.DEFAULT,
                         description="organism key, from GET /species")


@app.post("/jobs", status_code=202)
def post_job(req: JobRequest, con=Depends(get_con)):
    """Queue one miRNA. The worker runs it; poll GET /jobs/{job_id}."""
    _check_species(con, req.species)
    m = resolve.resolve_mirna(con, req.mirna, req.species)
    if not m:
        raise HTTPException(404, {"error": "mirna_not_found", "query": req.mirna,
                                  "species": req.species})
    if "accession" not in m:
        raise HTTPException(409, {"error": "mirna_ambiguous", "query": req.mirna,
                                  "candidates": m.get("candidates", [])})
    try:
        job_id = orchestrator.create_job(con, req.mirna, tools=req.tools,
                                         genes=req.genes, batch_id=req.batch_id,
                                         species=req.species)
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

# The regions a transcript is divided into. An export that asked for a region
# outside this set is a mistake on the caller's side, not an empty result.
REGIONS = {"5UTR", "CDS", "3UTR"}


def _where(job_id, tool, region, site_type, gene, regions=None,
           include_6mer=True, q=None):
    """Build the WHERE clause from whatever filters were supplied.

    `regions`, `include_6mer` and `q` exist so that an export can reproduce
    what the table is showing: those three are applied in the browser, and a
    file that ignored them would contain rows the screen was hiding without
    saying so anywhere.
    """
    parts, args = ["job_id = ?"], [job_id]
    for col, val in (("tool", tool), ("region", region), ("site_type", site_type)):
        if val:
            parts.append(col + " = ?")
            args.append(val)
    if gene:
        parts.append("(symbol = ? COLLATE NOCASE OR entrez = ?)")
        args += [gene, gene]
    if q:
        pat = "%" + q.replace("\\", "\\\\").replace("%", "\\%") \
                     .replace("_", "\\_") + "%"
        parts.append("(symbol LIKE ? ESCAPE '\\' COLLATE NOCASE "
                     "OR entrez LIKE ? ESCAPE '\\')")
        args += [pat, pat]
    if regions is not None:
        # A row with no region of its own is never hidden by a region box.
        # miRTarBase evidence is about the gene, not a place inside it, so
        # unticking 5'UTR must not make published evidence disappear - the
        # page's own region filter touches only seed and RNAhybrid rows.
        clause = "region IS NULL OR region = ''"
        if regions:
            clause += " OR region IN (" + ",".join("?" * len(regions)) + ")"
            args += list(regions)
        parts.append("(" + clause + ")")
    if not include_6mer:
        # 'Include 6mer sites' is a statement about the seed analyser's own
        # categories, so it must not reach into another tool's rows.
        parts.append("NOT (tool = 'seed' AND site_type = '6mer')")
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
    loaded = T.counts(con)
    return {"name": config.TOOL_NAME, "version": config.TOOL_VERSION,
            "description": config.TOOL_DESCRIPTION,
            "subtitle": config.TOOL_SUBTITLE,
            "species_loaded": [
                {"key": k, "common": sp.get(k)["common"],
                 "assembly": sp.get(k)["assembly"], "transcripts": n}
                for k, n in sorted(loaded.items())],
            "data_sources": [{"name": r[0], "version": r[1], "url": r[2],
                              "downloaded_on": r[3], "notes": r[4]}
                             for r in rows]}


@app.get("/genes/{gene}")
def read_gene(gene: str, species: str = sp.DEFAULT, con=Depends(get_con)):
    """The canonical transcript for one gene: its length and its region
    boundaries. The binding map draws itself from this.

    Scoped to one organism: gene symbols collide across species, so an
    unscoped lookup of PTEN would match human and mouse both and report
    the gene as ambiguous."""
    _check_species(con, species)
    g = resolve.resolve_gene(con, gene, species)
    if not g or "entrez" not in g:
        raise HTTPException(404, {"error": "gene_not_found", "query": gene,
                                  "species": species})
    hits = T.targets_for(con, [g["entrez"]], species)
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
def read_mirna(query: str, species: str = sp.DEFAULT, con=Depends(get_con)):
    """Resolve one miRNA and return what the query panel shows: accession,
    mature sequence, seed, and its TargetScan family if it has one.

    `species` only decides which prefix a bare name is completed with:
    "miR-21a-5p" becomes mmu-miR-21a-5p for mouse. A fully-qualified
    name from any organism still resolves."""
    m = resolve.resolve_mirna(con, query, species)
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
    """How to rank genes.

    The rule itself lives in ranking.py because the report ranks genes the
    same way; this is only the HTTP translation of a bad request.
    """
    try:
        return ranking.gene_order(sort)
    except ranking.BadSort as e:
        raise HTTPException(422, {"error": "bad_sort", "sort": sort,
                                  "message": str(e)})


@app.get("/jobs/{job_id}/genes")
def read_genes(job_id: str,
               sort: str = Query("gene", pattern="^[a-z_]+$"),
               gene: Optional[str] = None,
               q: Optional[str] = Query(None, max_length=60),
               limit: int = Query(10, ge=1, le=200),
               offset: int = Query(0, ge=0),
               con=Depends(get_con)):
    """One page of genes, with every record for those genes and the
    transcript geometry the binding map needs. The table is gene-level, so
    the API pages by gene rather than by row."""
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    order, oargs = _gene_order(sort)
    # ?gene= narrows the table to one gene: how the pathway panel jumps from a
    # term's gene list back to the binding sites that put it there.
    gclause, gargs = ("", [])
    if gene:
        gclause = " AND (symbol = ? COLLATE NOCASE OR entrez = ?)"
        gargs = [gene, gene]
    elif q:
        # ?q= searches every gene in the job, not the page on screen. Searching
        # the loaded page would silently miss a gene sitting at rank 300.
        pat = "%" + q.replace("\\", "\\\\").replace("%", "\\%") \
                     .replace("_", "\\_") + "%"
        gclause = (" AND (symbol LIKE ? ESCAPE '\\' COLLATE NOCASE "
                   "OR entrez LIKE ? ESCAPE '\\')")
        gargs = [pat, pat]
    total = con.execute("SELECT COUNT(DISTINCT symbol) FROM results "
                        "WHERE job_id=?" + gclause, [job_id] + gargs).fetchone()[0]
    syms = [r[0] for r in con.execute(
        "SELECT symbol FROM results WHERE job_id=?" + gclause + " GROUP BY symbol "
        "ORDER BY " + order + " LIMIT ? OFFSET ?",
        [job_id] + gargs + oargs + [limit, offset])]
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
    # The transcripts this job actually used, read back from the result
    # rows rather than re-derived from symbols plus a MANE filter. Two
    # reasons the old form broke once a second species existed: a
    # non-human transcript has no MANE row at all, so the binding map
    # came back empty; and symbols collide, so a shared symbol could
    # return the other organism's geometry. refseq is the primary key,
    # so this is exact.
    refs = sorted({d["refseq"] for d in out if d.get("refseq")})
    geom = []
    if refs:
        rqs = ",".join("?" * len(refs))
        geom = con.execute("SELECT entrez, symbol, refseq, length "
                           "FROM transcripts WHERE refseq IN (" + rqs + ")",
                           refs).fetchall()
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


class EnrichmentRequest(BaseModel):
    """The same tick boxes as /geneset, sent as a body - or, instead of any
    of them, an explicit gene list from a click on the agreement diagram.
    `included`/`excluded` name the tools that produced it, only so the
    stored run can describe itself in the same words as the region did."""
    seed: Optional[str] = None
    targetscan: Optional[str] = None
    rnahybrid: Optional[str] = None
    mirtarbase: Optional[str] = None
    regions: Optional[List[str]] = None
    match: str = Field("all", pattern="^(all|any)$")
    genes: Optional[List[str]] = None
    included: Optional[List[str]] = None
    excluded: Optional[List[str]] = None


def _spec(req):
    d = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    d["in"] = d.pop("included", None)
    d["out"] = d.pop("excluded", None)
    return d


@app.post("/jobs/{job_id}/enrichment", status_code=202)
def post_enrichment(job_id: str, req: EnrichmentRequest, force: bool = False,
                    con=Depends(get_con)):
    """Queue GO and KEGG over-representation for the genes the boxes select.

    Returns immediately; the same worker that runs jobs runs this. Poll
    GET /enrichment/{run_id}. Enrichment takes minutes, mostly waiting on the
    KEGG server, so it is never done inside the request.

    An identical filter already run on this job is handed back instead of
    computed again - unless the job has been re-run since, or force=true.
    """
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    spec = _spec(req)
    if not force:
        existing = enrichment.find(con, job_id, spec)
        if existing:
            r = enrichment.get_run(con, existing)
            if not r["stale"]:
                return {"run_id": existing, "status": r["status"], "reused": True,
                        "rule_sentence": r["rule_sentence"],
                        "n_terms": r["n_terms"]}
    try:
        run_id = enrichment.create(con, job_id, spec)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, {"error": "bad_request", "message": str(e)})
    return {"run_id": run_id, "status": "queued", "reused": False}


@app.get("/jobs/{job_id}/enrichment")
def list_enrichment(job_id: str, con=Depends(get_con)):
    """Every enrichment ever run on this job, newest first. Nothing is
    deleted, so this is also the history."""
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    return {"job_id": job_id, "runs": enrichment.list_runs(con, job_id)}


@app.get("/enrichment/{run_id}")
def read_enrichment(run_id: str,
                    source: Optional[str] = None,
                    q: Optional[str] = Query(None, max_length=120),
                    include_genes: bool = False,
                    limit: int = Query(50, ge=1, le=1000),
                    offset: int = Query(0, ge=0),
                    con=Depends(get_con)):
    """One enrichment: how it was run, and a page of its terms.

    Every term carries the four integers of its own hypergeometric test, so a
    reader can recompute the p-value without this tool. They are per term and
    not per run: the annotation covers a different number of genes in each
    ontology, and KEGG covers about half the genome.
    """
    r = enrichment.get_run(con, run_id)
    if r is None:
        raise HTTPException(404, {"error": "run_not_found", "run_id": run_id})
    if not include_genes:
        r.pop("genes")
    # terms_by_source is never filtered by q: it labels the tabs, and a tab
    # whose count changed as you typed would be unreadable.
    by_source = {s: n for s, n in con.execute(
        "SELECT source, COUNT(*) FROM enrichment_terms WHERE run_id=? "
        "GROUP BY source ORDER BY source", (run_id,))}
    return {"run": r, "terms_by_source": by_source,
            "total": enrichment.count_terms(con, run_id, source, q),
            "in_source": by_source.get(source, sum(by_source.values())),
            "limit": limit, "offset": offset, "source": source, "q": q,
            "terms": enrichment.terms(con, run_id, source, limit, offset, q)}


# ------------------------------------------------------------------ export
# Tab-separated, not comma: gene descriptions and GO term names contain commas
# and would need quoting, which spreadsheets and R read inconsistently. A TSV
# opens correctly in Excel, LibreOffice, pandas and read.delim with no options.

def _tsv(rows, cols, filename, header=None):
    def cell(v):
        if v is None:
            return ""
        # a stray tab or newline would shift every later column silently
        return str(v).replace("\t", " ").replace("\r", " ").replace("\n", " ")

    def gen():
        # '#' lines first, then exactly one header row, then the data. A
        # reader that skips comments sees a plain TSV; one that doesn't
        # still has every version and filter in front of it.
        for line in (header or []):
            yield line + "\n"
        yield "\t".join(cols) + "\n"
        for r in rows:
            yield "\t".join(cell(r[c] if isinstance(r, dict) else r[i])
                            for i, c in enumerate(cols)) + "\n"

    return StreamingResponse(
        gen(), media_type="text/tab-separated-values; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename})


@app.get("/jobs/{job_id}/results.tsv")
def export_results(job_id: str,
                   tool: Optional[str] = None,
                   region: Optional[str] = None,
                   site_type: Optional[str] = None,
                   gene: Optional[str] = None,
                   regions: Optional[str] = None,
                   include_6mer: bool = True,
                   q: Optional[str] = Query(None, max_length=60),
                   con=Depends(get_con)):
    """Every row of a job, unpaginated, exactly as stored.

    No limit: an export that silently stopped at 100 rows would be worse than
    no export. Scores stay in their own columns and are never combined.

    `regions` is a comma-separated list and is deliberately distinguishable
    from absent: omitted means no region filter, empty means every region box
    was unticked. Those are different questions and must give different files.
    """
    st = orchestrator.job_status(con, job_id)
    if st is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    regs = None
    if regions is not None:
        regs = [r.strip() for r in regions.split(",") if r.strip()]
        bad = [r for r in regs if r not in REGIONS]
        if bad:
            raise HTTPException(422, {"error": "bad_region", "regions": bad,
                                      "allowed": sorted(REGIONS)})
    where, args = _where(job_id, tool, region, site_type, gene,
                         regions=regs, include_6mer=include_6mer, q=q)
    # Read the rows and spread `extra` into named columns. No TSV this tool
    # produces contains JSON: a reader should reach aggregate_pct by naming a
    # column, not by parsing an object out of a cell.
    rows = []
    for r in con.execute("SELECT " + ", ".join(RESULT_COLS) + " FROM results "
                         "WHERE " + where + " ORDER BY symbol, tool, pos_start",
                         args):
        d = dict(zip(RESULT_COLS, r))
        d["extra"] = json.loads(d["extra"]) if d["extra"] else None
        rows.append(d)
    base = [c for c in RESULT_COLS if c != "extra"]
    cols = flatten.columns(base, rows)
    cells = flatten.rows_as_cells(rows, cols, base)
    name = "%s_%s_results.tsv" % (st["params"]["mirna_name"].replace("/", "-"),
                                  job_id)
    head = provenance.results(
        con, st,
        filters={"tool": tool, "region": region, "site_type": site_type,
                 "gene": gene, "gene_search": q,
                 "regions": ",".join(regs) if regs else
                            ("none ticked" if regs == [] else None),
                 "6mer_sites": None if include_6mer else "excluded"},
        order="symbol, tool, pos_start")
    return _tsv(cells, cols, name, head)


@app.get("/jobs/{job_id}/results.xlsx")
def export_results_xlsx(job_id: str,
                        tool: Optional[str] = None,
                        region: Optional[str] = None,
                        site_type: Optional[str] = None,
                        gene: Optional[str] = None,
                        regions: Optional[str] = None,
                        include_6mer: bool = True,
                        q: Optional[str] = Query(None, max_length=60),
                        con=Depends(get_con)):
    """The same rows as results.tsv, arranged for a spreadsheet.

    A separate format rather than a replacement: the TSV keeps its '#'
    provenance and its JSON `extra` because R and pandas read both correctly,
    and this file flattens `extra` into columns and puts provenance on its
    own sheet because a spreadsheet reads neither.
    """
    st = orchestrator.job_status(con, job_id)
    if st is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    regs = None
    if regions is not None:
        regs = [r.strip() for r in regions.split(",") if r.strip()]
        bad = [r for r in regs if r not in REGIONS]
        if bad:
            raise HTTPException(422, {"error": "bad_region", "regions": bad,
                                      "allowed": sorted(REGIONS)})
    where, args = _where(job_id, tool, region, site_type, gene,
                         regions=regs, include_6mer=include_6mer, q=q)
    cur = con.execute("SELECT " + ", ".join(RESULT_COLS) + " FROM results "
                      "WHERE " + where + " ORDER BY symbol, tool, pos_start",
                      args)
    rows = []
    for r in cur.fetchall():
        d = dict(zip(RESULT_COLS, r))
        d["extra"] = json.loads(d["extra"]) if d["extra"] else None
        rows.append(d)
    prov = provenance.results(
        con, st,
        filters={"tool": tool, "region": region, "site_type": site_type,
                 "gene": gene, "gene_search": q,
                 "regions": ",".join(regs) if regs else
                            ("none ticked" if regs == [] else None),
                 "6mer_sites": None if include_6mer else "excluded"},
        order="symbol, tool, pos_start")
    try:
        blob = xlsx_export.build(rows, prov_lines=prov,
                                 tool_runs=st["tools"])
    except RuntimeError as e:
        raise HTTPException(501, {"error": "xlsx_unavailable",
                                  "message": str(e)})
    name = "%s_%s_results.xlsx" % (
        st["params"]["mirna_name"].replace("/", "-"), job_id)
    return StreamingResponse(
        iter([blob]),
        media_type="application/vnd.openxmlformats-officedocument."
                   "spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="%s"' % name})


ENR_COLS = ("source", "term_id", "description", "k_in_term_and_list",
            "n_in_list", "k_in_term_and_background", "n_in_background",
            "p_value", "p_adjust", "q_value", "genes")


@app.get("/enrichment/{run_id}/terms.tsv")
def export_enrichment(run_id: str, source: Optional[str] = None,
                      q: Optional[str] = None, con=Depends(get_con)):
    """Every enriched term with the four integers behind its p-value, so the
    statistics can be redone from the file alone."""
    r = enrichment.get_run(con, run_id)
    if r is None:
        raise HTTPException(404, {"error": "run_not_found", "run_id": run_id})
    rows = enrichment.terms(con, run_id, source, None, 0, q)
    head = provenance.enrichment(con, r, source, q)
    # 7.15781004119207e-06 is float repr noise, not precision anyone reports.
    # Six significant figures is far beyond what a p-value is quoted to, and
    # nothing is lost: the exact value is recomputable from the four k/n
    # integers in the same row, which is why they are stored.
    out = []
    for t in rows:
        d = dict(t)
        for c in ("p_value", "p_adjust", "q_value"):
            if isinstance(d.get(c), float):
                d[c] = "%.6g" % d[c]
        # slash-separated in the database; commas read as a list to a person
        # and split as one in any language
        if d.get("genes"):
            d["genes"] = d["genes"].replace("/", ", ")
        out.append(d)
    return _tsv(out, list(ENR_COLS), "%s_enrichment.tsv" % run_id, head)


@app.get("/enrichment/{run_id}/terms.xlsx")
def export_enrichment_xlsx(run_id: str, source: Optional[str] = None,
                           q: Optional[str] = None, con=Depends(get_con)):
    """The same terms as terms.tsv, one sheet per ontology.

    Split by ontology rather than tabbed on a source column, because two
    ontologies are tested against different annotated backgrounds and have
    never belonged in one ranking.
    """
    r = enrichment.get_run(con, run_id)
    if r is None:
        raise HTTPException(404, {"error": "run_not_found", "run_id": run_id})
    rows = enrichment.terms(con, run_id, source, None, 0, q)
    head = provenance.enrichment(con, r, source, q)
    try:
        blob = xlsx_export.build_enrichment(rows, head)
    except RuntimeError as e:
        raise HTTPException(501, {"error": "xlsx_unavailable",
                                  "message": str(e)})
    return StreamingResponse(
        iter([blob]),
        media_type="application/vnd.openxmlformats-officedocument."
                   "spreadsheetml.sheet",
        headers={"Content-Disposition":
                 'attachment; filename="%s_enrichment.xlsx"' % run_id})


@app.get("/enrichment/{run_id}/genes.txt")
def export_enrichment_genes(run_id: str, con=Depends(get_con)):
    """The gene ids this run actually tested - the list behind every p-value."""
    r = enrichment.get_run(con, run_id)
    if r is None:
        raise HTTPException(404, {"error": "run_not_found", "run_id": run_id})
    body = "\n".join(r["genes"]) + "\n"
    return StreamingResponse(
        iter([body]), media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition":
                 'attachment; filename="%s_genes.txt"' % run_id})


@app.get("/jobs/{job_id}/network")
def read_network(job_id: str,
                 sort: str = Query("gene", pattern="^[a-z_]+$"),
                 top_n: int = Query(50, ge=2, le=500),
                 enrichment_run: Optional[str] = None,
                 min_shared: int = Query(1, ge=1, le=50),
                 max_edges: int = Query(network.MAX_PAIR_EDGES, ge=10,
                                        le=5000),
                 con=Depends(get_con)):
    """Nodes and edges for the network view.

    Computed per request rather than queued: it is two indexed reads and some
    counting, milliseconds even at 500 genes. Nothing is stored, because
    nothing here is new - it is the same rows the table shows, arranged as a
    graph.
    """
    try:
        return network.build(con, job_id, sort=sort, top_n=top_n,
                             enrichment_run=enrichment_run,
                             min_shared=min_shared, max_edges=max_edges)
    except ranking.BadSort as e:
        raise HTTPException(422, {"error": "bad_sort", "sort": sort,
                                  "message": str(e)})
    except ValueError as e:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id,
                                  "message": str(e)})


# -------------------------------------------------------------- agreement

def _regs(regions):
    """The shared region-filter parse. Absent and empty mean different
    things and must stay distinguishable all the way down."""
    if regions is None:
        return None
    regs = [r.strip() for r in regions.split(",") if r.strip()]
    bad = [r for r in regs if r not in REGIONS]
    if bad:
        raise HTTPException(422, {"error": "bad_region", "regions": bad,
                                  "allowed": sorted(REGIONS)})
    return regs


def _csv(v):
    return [x.strip() for x in (v or "").split(",") if x.strip()]


# Declared before /agreement so the bare route cannot swallow this path -
# the same ordering rule /reports/{id}.html needs.
@app.get("/jobs/{job_id}/agreement/genes")
def read_agreement_genes(job_id: str,
                         inc: str = Query(..., alias="in"),
                         out: Optional[str] = None,
                         regions: Optional[str] = None,
                         include_6mer: bool = True,
                         q: Optional[str] = Query(None, max_length=60),
                         scanmir_canonical: bool = True,
                         limit: int = Query(100, ge=1, le=20000),
                         offset: int = Query(0, ge=0),
                         con=Depends(get_con)):
    """The genes in one exclusive region of the agreement diagram.

    `in` and `out` are comma-separated tool names. Both matter: clicking a
    Venn region asks for the genes those tools found and the others did not,
    which is not the same question as "found by these tools".

    The ceiling is 20,000, not the usual page size, because two callers need
    every gene in the region at once rather than a page of it: the CSV
    export and the "run enrichment on these genes" button, which has to hand
    enrichment.create() the complete list or the p-values would be wrong.
    19,363 MANE Select genes is the largest a region could ever be.
    """
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    where, args = _where(job_id, None, None, None, None,
                         regions=_regs(regions), include_6mer=include_6mer, q=q)
    try:
        return agreement.region_genes(
            con, job_id, _csv(inc), _csv(out), where=where, args=args,
            scanmir_canonical=scanmir_canonical, limit=limit, offset=offset)
    except agreement.BadRequest as e:
        raise HTTPException(422, {"error": "bad_region_request",
                                  "message": str(e)})


@app.get("/jobs/{job_id}/agreement")
def read_agreement(job_id: str,
                   tools: Optional[str] = None,
                   regions: Optional[str] = None,
                   include_6mer: bool = True,
                   q: Optional[str] = Query(None, max_length=60),
                   scanmir_canonical: bool = True,
                   con=Depends(get_con)):
    """How much the tools agree, as set sizes and exclusive regions.

    Computed over the same filtered rows the results table is showing, and
    the filters are echoed back so a figure can caption itself. A diagram
    whose numbers disagree with the table above it reads as a bug.

    `display` says whether to draw a Venn or an UpSet plot: beyond four sets
    a Venn needs ellipses and 31 regions, several too thin to click.
    """
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    regs = _regs(regions)
    where, args = _where(job_id, None, None, None, None,
                         regions=regs, include_6mer=include_6mer, q=q)
    try:
        return agreement.build(
            con, job_id, tools=_csv(tools) or None, where=where, args=args,
            scanmir_canonical=scanmir_canonical,
            filters={"regions": regs, "include_6mer": include_6mer, "q": q})
    except agreement.BadRequest as e:
        raise HTTPException(422, {"error": "bad_agreement_request",
                                  "message": str(e)})


# ------------------------------------------------------------------ reports

class ReportRequest(BaseModel):
    """What to put in a report. Both fields are fixed at request time."""
    sort: str = Field("gene", description="the gene ranking to take the top N by")
    top_n: int = Field(50, ge=1, le=2000)
    terms_per_source: int = Field(
        20, ge=0, le=2000,
        description="enriched terms per ontology; 0 means every term")
    maps_for: int = Field(
        10, ge=0, le=100,
        description="how many genes get a binding map; 0 draws none")
    network: bool = Field(True, description="include the target network")


@app.post("/jobs/{job_id}/reports", status_code=202)
def post_report(job_id: str, req: ReportRequest, con=Depends(get_con)):
    """Queue an HTML report for one job. Poll GET /reports/{report_id}.

    Never reused the way an enrichment run is: a report is cheap to redo and
    its point is to be a dated document, so asking twice should give two.
    """
    try:
        report_id = R.create(con, job_id, req.model_dump())
    except ValueError as e:
        raise HTTPException(422, {"error": "bad_request", "message": str(e)})
    return {"report_id": report_id, "status": "queued"}


@app.get("/jobs/{job_id}/reports")
def list_reports(job_id: str, con=Depends(get_con)):
    """Every report ever built for this job, newest first."""
    if orchestrator.job_status(con, job_id) is None:
        raise HTTPException(404, {"error": "job_not_found", "job_id": job_id})
    return {"job_id": job_id, "reports": R.list_reports(con, job_id)}


# Declared before /reports/{report_id}: routes match in declaration order, and
# a bare {report_id} happily swallows "rep_abc.html" as a report id. The more
# specific path has to come first or the document is unreachable.
@app.get("/reports/{report_id}.html")
def read_report_html(report_id: str, download: bool = False,
                     con=Depends(get_con)):
    """The report itself.

    Served inline by default so it opens in the browser and prints straight
    to PDF - which is how this tool produces a PDF without a PDF toolchain.
    ?download=1 saves it instead.
    """
    r = R.get(con, report_id, include_html=True)
    if r is None:
        raise HTTPException(404, {"error": "report_not_found",
                                  "report_id": report_id})
    if r["status"] != "done":
        raise HTTPException(409, {"error": "report_not_ready",
                                  "status": r["status"], "error_": r["error"]})
    headers = {}
    if download:
        headers["Content-Disposition"] = \
            'attachment; filename="%s_report.html"' % report_id
    return StreamingResponse(iter([r["html"]]), media_type="text/html; charset=utf-8",
                             headers=headers)


@app.get("/reports/{report_id}")
def read_report(report_id: str, con=Depends(get_con)):
    """Status and metadata. The document itself is at /reports/{id}.html."""
    r = R.get(con, report_id)
    if r is None:
        raise HTTPException(404, {"error": "report_not_found",
                                  "report_id": report_id})
    return r


# Mounted last: it claims "/", so every real endpoint must be declared above.
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
# ── batches ────────────────────────────────────────────────────────────
# Several miRNAs in one request. Each becomes an ordinary job, so every
# existing view keeps working; the batch only adds the comparison
# between them.
import batch as B


class BatchRequest(BaseModel):
    mirnas: List[str]
    tools: Optional[List[str]] = None
    genes: Optional[List[str]] = None
    species: Optional[str] = None


@app.post("/batches", status_code=202)
def post_batch(req: BatchRequest, con=Depends(get_con)):
    species = req.species or sp.DEFAULT
    _check_species(con, species)
    try:
        return B.create(con, req.mirnas, tools=req.tools, genes=req.genes,
                        species=species)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str, con=Depends(get_con)):
    js = B.jobs(con, batch_id)
    if not js:
        raise HTTPException(status_code=404, detail="no such batch")
    # whatever the job table calls finished
    DONE = ("done", "ok", "failed", "error", "cancelled")
    done = sum(1 for j in js if (j["status"] or "").lower() in DONE)
    return {"batch_id": batch_id, "n_jobs": len(js), "n_done": done,
            "jobs": js}


@app.get("/batches/{batch_id}/intersection")
def get_batch_intersection(batch_id: str,
                           min_count: Optional[int] = None,
                           site_types: Optional[str] = None,
                           tools: Optional[str] = None,
                           limit: int = 500,
                           con=Depends(get_con)):
    if not B.jobs(con, batch_id):
        raise HTTPException(status_code=404, detail="no such batch")
    st = [s for s in (site_types or "").split(",") if s]
    tl = [t for t in (tools or "").split(",") if t]
    out = B.intersection(con, batch_id, min_count, st or None, tl or None)
    out["genes"] = out["genes"][:max(1, int(limit))]
    return out


@app.post("/batches/{batch_id}/enrichment", status_code=202)
def post_batch_enrichment(batch_id: str,
                          min_count: Optional[int] = None,
                          site_types: Optional[str] = None,
                          tools: Optional[str] = None,
                          con=Depends(get_con)):
    """Enrichment on the shared genes.

    Runs against the first job in the batch, so the organism and the
    background come from the batch itself.
    """
    js = B.jobs(con, batch_id)
    if not js:
        raise HTTPException(status_code=404, detail="no such batch")
    st = [s for s in (site_types or "").split(",") if s]
    tl = [t for t in (tools or "").split(",") if t]
    hit = B.intersection(con, batch_id, min_count, st or None, tl or None)
    ids = [g["entrez"] for g in hit["genes"]]
    if not ids:
        raise HTTPException(status_code=400,
                            detail="no gene is shared by that many miRNAs")
    try:
        run_id = enrichment.create(con, js[0]["job_id"], {"genes": ids})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"run_id": run_id, "n_genes": len(ids),
            "min_count": hit["min_count"], "n_mirnas": hit["n_mirnas"]}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")

