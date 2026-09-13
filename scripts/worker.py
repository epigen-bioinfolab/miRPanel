"""Background worker: run queued jobs and queued enrichments, one at a time.

Assumes a single worker. next_queued() claims atomically, so several
workers would also be safe, but requeue_stale() on startup would not be.

Jobs are drained before enrichments: an enrichment reads a job's results, so
finishing the job it depends on first is never the wrong order.
"""
import sqlite3, sys, time
sys.path.insert(0, "src")
import enrichment as E
import orchestrator as O

DB = "data/processed/mirna.db"
IDLE = 2.0

con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode = WAL")
con.execute("PRAGMA busy_timeout = 15000")

for what, n in (("job", O.requeue_stale(con)), ("enrichment", E.requeue_stale(con))):
    if n:
        print(O.now(), "requeued", n, "stale", what + "(s)", flush=True)
print(O.now(), "worker started, polling every %.0fs" % IDLE, flush=True)

while True:
    job = O.next_queued(con)
    if job is not None:
        print(O.now(), "running", job, flush=True)
        try:
            total = O.run_job(con, job)
            print(O.now(), "done   ", job, total, "results", flush=True)
        except Exception as exc:
            print(O.now(), "failed ", job, repr(exc), flush=True)
        continue

    run = E.next_queued(con)
    if run is not None:
        print(O.now(), "running", run, flush=True)
        try:
            E.execute(con, run)
            r = E.get_run(con, run)
            print(O.now(), "done   ", run, r["n_terms"], "terms in %ss"
                  % r["seconds"], flush=True)
        except Exception as exc:
            print(O.now(), "failed ", run, repr(exc), flush=True)
        continue

    time.sleep(IDLE)
