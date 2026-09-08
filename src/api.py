"""HTTP API over the orchestrator. Read-only, except for creating jobs."""
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
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
