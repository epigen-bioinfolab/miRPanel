#!/usr/bin/env python3
"""Delete old searches and reclaim the disk they hold.

Every search stores one row per binding site, so the database grows with
use: a few hundred whole-transcriptome searches add several GB. The
reference data is never touched by this script - only jobs, their results,
their enrichment runs and their reports.

    python3 scripts/prune_jobs.py                 # show what would go
    python3 scripts/prune_jobs.py --days 30 --yes # delete it
    python3 scripts/prune_jobs.py --all --yes     # every search, keep the data

VACUUM runs afterwards to return the space to the filesystem, and it needs
free disk roughly equal to the finished size of the database.
"""

import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "processed", "mirna.db")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=30,
                    help="delete searches finished more than this many days "
                         "ago (default 30)")
    ap.add_argument("--all", action="store_true",
                    help="delete every search, whatever its age")
    ap.add_argument("--yes", action="store_true",
                    help="actually delete; without it nothing is changed")
    ap.add_argument("--no-vacuum", action="store_true",
                    help="skip VACUUM; rows go but the file does not shrink")
    ap.add_argument("--db", default=DB, help="path to mirna.db")
    a = ap.parse_args()

    if not os.path.exists(a.db):
        sys.exit("No database at %s" % a.db)

    before = os.path.getsize(a.db)
    con = sqlite3.connect(a.db)
    con.execute("PRAGMA foreign_keys=ON")

    if a.all:
        where, args, what = "1=1", (), "every search"
    else:
        where = ("COALESCE(finished_at, created_at) < "
                 "datetime('now', ?)")
        args = ("-%d days" % a.days,)
        what = "searches older than %d days" % a.days

    ids = [r[0] for r in con.execute(
        "SELECT job_id FROM jobs WHERE " + where, args)]
    total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    if not ids:
        print("Nothing to delete: no %s (of %d in total)." % (what, total))
        return

    qs = ",".join("?" * len(ids))
    rows = con.execute(
        "SELECT COUNT(*) FROM results WHERE job_id IN (%s)" % qs, ids).fetchone()[0]

    print("Database   %s  (%.2f GB)" % (a.db, before / 1e9))
    print("Searches   %d of %d match: %s" % (len(ids), total, what))
    print("Rows       %s result rows would go" % format(rows, ","))

    if not a.yes:
        print("\nNothing was changed. Add --yes to delete.")
        return

    print("\nDeleting...")
    for table, col in (("results", "job_id"),
                       ("tool_runs", "job_id"),
                       ("reports", "job_id"),
                       ("enrichment_runs", "job_id"),
                       ("jobs", "job_id")):
        try:
            cur = con.execute(
                "DELETE FROM %s WHERE %s IN (%s)" % (table, col, qs), ids)
            print("  %-18s %s rows" % (table, format(cur.rowcount, ",")))
        except sqlite3.Error as e:
            print("  %-18s skipped (%s)" % (table, e))

    # enrichment_terms hangs off a run, which may now be gone
    try:
        cur = con.execute("""DELETE FROM enrichment_terms WHERE run_id NOT IN
                             (SELECT run_id FROM enrichment_runs)""")
        print("  %-18s %s rows" % ("enrichment_terms", format(cur.rowcount, ",")))
    except sqlite3.Error as e:
        print("  %-18s skipped (%s)" % ("enrichment_terms", e))

    con.commit()

    if a.no_vacuum:
        print("\nRows deleted. VACUUM skipped, so the file is the same size.")
    else:
        print("\nVACUUM - this takes a while and needs free disk...")
        con.isolation_level = None
        con.execute("VACUUM")
        print("done.")

    con.close()
    after = os.path.getsize(a.db)
    print("\n%.2f GB -> %.2f GB  (%.2f GB reclaimed)"
          % (before / 1e9, after / 1e9, (before - after) / 1e9))


if __name__ == "__main__":
    main()
