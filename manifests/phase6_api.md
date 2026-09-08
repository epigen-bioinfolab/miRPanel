# Phase 6 — HTTP API

FastAPI over `src/orchestrator.py`. No new tables, no changes to the science.
Run: `uvicorn api:app --app-dir src --port 8000`  ·  docs at `/docs`

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness only |
| GET | `/tools` | registry META: score_type, better, categories, gives_position, slow |
| POST | `/jobs` | resolve, validate, queue. 202 with the job record |
| GET | `/jobs/{id}` | status, timings, per-tool `tool_runs` |
| GET | `/jobs/{id}/results` | one page of results, filtered and sorted |

## Decisions

- **Always queue.** A transcriptome-wide RNAhybrid job takes 13.5 minutes;
  no HTTP request may hold a connection that long. One code path for every
  job. `scripts/run_job.py` still runs inline for development.
- **One SQLite connection per request**, opened through `db.connect()` by a
  FastAPI dependency. WAL means readers never block the worker.
- **Sorting reads direction from the tool, never from the API.**
  `sort=score` without `?tool=` is a 422: scores from different tools are
  not comparable, so the server refuses to pretend otherwise. `sort=score`
  on seed is a 422 too — seed reports a category. `sort=site_type` orders
  by the tool's own published `categories`.
- **Errors are structured**: `mirna_not_found` (404), `mirna_ambiguous`
  (409, with candidate accessions), `bad_request` (422), `job_not_found`
  (404).

## Fixes this phase forced

- `create_job` now resolves **gene** identifiers itself and rejects unknown
  genes and genes with no MANE Select transcript. Previously the CLI
  resolved them by hand, so the API's first real request scanned zero
  transcripts and every tool reported `ok, 0 results` — indistinguishable
  from a true negative. Fixed at the gate, so every caller benefits.
- `run_job` refuses to report `ok` on an empty target set.
- `create_job` rejects unknown tool names at creation instead of failing
  minutes later inside the worker.
- `db.connect()` sets `busy_timeout = 15000`; only `worker.py` had it.
- A categorical tool (`better: None`) must publish `categories`, best
  first, or `check_meta` refuses to load it. seed publishes
  `8mer > 7mer-m8 > 7mer-A1 > 6mer`, so no frontend has to invent a ranking.

## Verified

`scripts/test_api.py` — 21 assertions, in-process, no server needed, cleans
up the job it creates. Covers every endpoint, every error path, the sort
rules, and the PDCD4 known-answer (8mer at 1805, context++ −0.503,
59 strong experiments).

Transcriptome-wide through the API: **13,920 results** —
seed 10,254 · targetscan 2,598 · mirtarbase 1,068. Identical to the Phase 5
CLI numbers from a different code path.

## Known gaps

- No response models, so `/docs` shows `"string"` for every 200 body.
  Deferred to the end of Phase 7, when the frontend has settled the shape.
- No CORS yet — needed as soon as the frontend runs on another origin.
- No rate limiting or auth. Fine for local use; not for a public server.
- `scripts/run_job.py` still resolves genes itself. Harmless (the resolver
  is idempotent on Entrez ids) but duplicated logic worth deleting.
