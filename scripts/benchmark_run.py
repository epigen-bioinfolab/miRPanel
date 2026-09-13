"""Queue one transcriptome-wide job per benchmark miRNA.

    python scripts/benchmark_run.py [--dry-run] [--force]

Reads data/tmp/benchmark_sets.json, queues a job for each miRNA with all four
tools, and records the job ids back into that file. Runs nothing itself: the
worker does the work, roughly four minutes per miRNA because RNAhybrid folds
every transcript. Eight miRNAs is about half an hour.

    nohup python scripts/worker.py > worker.log 2>&1 &
    tail -f worker.log

Jobs are transcriptome-wide on purpose. Restricting them to the benchmark
genes would be faster and wrong: a tool that only ever sees 400 genes has not
been asked the question the tool actually answers, and the false-positive
rate over ~18,000 unreported genes is the number we came for.

An existing finished job for the same miRNA with the same four tools and no
gene restriction is reused rather than repeated - which is why miR-21 usually
costs nothing here.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, "src")
import db
import orchestrator

TOOLS = ["seed", "rnahybrid", "targetscan", "mirtarbase"]
SETS = os.path.join("data", "tmp", "benchmark_sets.json")
BATCH = "benchmark"

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--force", action="store_true",
                help="queue a fresh job even if a usable one exists")
a = ap.parse_args()

if not os.path.exists(SETS):
    sys.exit("no %s - run scripts/benchmark_sets.py first" % SETS)
data = json.load(open(SETS))
con = db.connect()


def existing(accession):
    """A finished transcriptome-wide job with all four tools, if there is one."""
    for job_id, params in con.execute(
            "SELECT job_id, params FROM jobs WHERE status='done' "
            "ORDER BY created_at DESC"):
        p = json.loads(params)
        if (p.get("mirna_acc") == accession and not p.get("genes")
                and set(p.get("tools") or []) == set(TOOLS)):
            return job_id
    return None


print("%-20s %-14s %s" % ("miRNA", "accession", "job"))
queued = 0
for acc, s in data["sets"].items():
    have = None if a.force else existing(acc)
    if have:
        s["job_id"] = have
        print("%-20s %-14s %s  (reused)" % (s["name"], acc, have))
        continue
    if a.dry_run:
        print("%-20s %-14s would queue" % (s["name"], acc))
        continue
    try:
        job_id = orchestrator.create_job(con, acc, tools=TOOLS,
                                         batch_id=BATCH)
    except ValueError as e:
        print("%-20s %-14s FAILED: %s" % (s["name"], acc, e))
        continue
    s["job_id"] = job_id
    queued += 1
    print("%-20s %-14s %s  (queued)" % (s["name"], acc, job_id))

if not a.dry_run:
    json.dump(data, open(SETS, "w"), indent=1)
    print("\njob ids written back into %s" % SETS)
    print("%d queued, %d reused." % (queued, len(data["sets"]) - queued))
    if queued:
        print("\nStart the worker if it is not already running:")
        print("    nohup python scripts/worker.py > worker.log 2>&1 &")
        print("    tail -f worker.log")
        print("\nRoughly %d minutes of work." % (queued * 4))
