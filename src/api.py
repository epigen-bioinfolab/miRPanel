"""HTTP API over the orchestrator. Read-only, except for creating jobs."""
from fastapi import FastAPI
from tools import registry

app = FastAPI(title="miRNA target tool", version="0.1")


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
