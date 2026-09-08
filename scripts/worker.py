"""Background worker: run queued jobs, one at a time.

Assumes a single worker. next_queued() claims atomically, so several
workers would also be safe, but requeue_stale() on startup would not be.
"""
import sqlite3, sys, time
sys.path.insert(0, "src")
import orchestrator as O

DB = "data/processed/mirna.db"
IDLE = 2.0

con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode = WAL")
con.execute("PRAGMA busy_timeout = 15000")

n = O.requeue_stale(con)
if n:
    print(O.now(), "requeued", n, "stale job(s)", flush=True)
print(O.now(), "worker started, polling every %.0fs" % IDLE, flush=True)

while True:
    job = O.next_queued(con)
    if job is None:
        time.sleep(IDLE)
        continue
    print(O.now(), "running", job, flush=True)
    try:
        total = O.run_job(con, job)
        print(O.now(), "done   ", job, total, "results", flush=True)
    except Exception as exc:
        print(O.now(), "failed ", job, repr(exc), flush=True)
