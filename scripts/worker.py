"""Background worker: run queued jobs, enrichments and reports, one at a time.

Assumes a single worker. next_queued() claims atomically, so several
workers would also be safe, but requeue_stale() on startup would not be.

The queues are drained in dependency order: an enrichment reads a job's
results, and a report reads both, so finishing what a thing depends on
first is never the wrong order.
"""
import sys, time
sys.path.insert(0, "src")
import db
import enrichment as E
import orchestrator as O
import report as RP

DB = "data/processed/mirna.db"
IDLE = 2.0

# db.connect applies schema.sql as well as the pragmas, so the worker can be
# started before the API has ever run without tripping over a table that does
# not exist yet.
con = db.connect(DB)

for what, n in (("job", O.requeue_stale(con)),
                ("enrichment", E.requeue_stale(con)),
                ("report", RP.requeue_stale(con))):
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

    rep = RP.next_queued(con)
    if rep is not None:
        print(O.now(), "running", rep, flush=True)
        try:
            RP.execute(con, rep)
            r = RP.get(con, rep)
            print(O.now(), "done   ", rep, r["n_genes"], "genes,",
                  r["bytes"], "bytes in %ss" % r["seconds"], flush=True)
        except Exception as exc:
            print(O.now(), "failed ", rep, repr(exc), flush=True)
        continue

    time.sleep(IDLE)
