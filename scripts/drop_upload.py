# -*- coding: utf-8 -*-
"""Remove an uploaded organism from the database.

A test upload left in the shipped database appears in every user's
organism list. This finds every row belonging to one upload and, with
--yes, deletes it.

    python3 drop_upload.py                 # show what would go
    python3 drop_upload.py --yes           # delete it
    python3 drop_upload.py --species NAME  # pick one, if there are several
"""

import argparse
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), "data", "processed", "mirna.db")

ap = argparse.ArgumentParser()
ap.add_argument("--yes", action="store_true", help="actually delete")
ap.add_argument("--species", help="which upload, e.g. upload:up_3ef3d755b81d")
ap.add_argument("--no-vacuum", action="store_true")
a = ap.parse_args()

if not os.path.exists(DB):
    sys.exit("No database at %s - run this from the project root." % DB)

con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys=ON")


def columns(table):
    return [r[1] for r in con.execute("PRAGMA table_info(%s)" % table)]


tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' "
    "AND name NOT LIKE 'sqlite_%'")]

# which uploads are in here
uploads = [r[0] for r in con.execute(
    "SELECT DISTINCT species FROM transcripts WHERE species LIKE 'upload:%'")]

if not uploads:
    print("No uploaded organisms in the database.")
    sys.exit(0)

if a.species:
    if a.species not in uploads:
        sys.exit("Not found: %s\nPresent: %s" % (a.species, ", ".join(uploads)))
    target = a.species
elif len(uploads) == 1:
    target = uploads[0]
else:
    sys.exit("Several uploads present, pick one with --species:\n  " +
             "\n  ".join(uploads))

upload_id = target.split(":", 1)[1]
print("Upload     %s" % target)
print("Database   %s  (%.2f GB)\n" % (DB, os.path.getsize(DB) / 1e9))

# rows that name the species directly
direct = [t for t in tables if "species" in columns(t)]

# rows that hang off this upload's transcripts or genes
tx = [r[0] for r in con.execute(
    "SELECT refseq FROM transcripts WHERE species=?", (target,))]
genes = [r[0] for r in con.execute(
    "SELECT DISTINCT entrez FROM genes WHERE species=?", (target,))] \
    if "species" in columns("genes") else []

plan = []
for t in sorted(direct):
    n = con.execute("SELECT COUNT(*) FROM %s WHERE species=?" % t,
                    (target,)).fetchone()[0]
    if n:
        plan.append((t, "species=?", (target,), n))

# anything keyed to those transcripts or genes but without a species column
for t in sorted(set(tables) - set(direct)):
    cols = columns(t)
    for col, ids in (("refseq", tx), ("transcript", tx),
                     ("entrez", genes), ("gene", genes)):
        if col in cols and ids:
            q = ("SELECT COUNT(*) FROM %s WHERE %s IN "
                 "(SELECT refseq FROM transcripts WHERE species=?)" % (t, col)
                 if ids is tx else
                 "SELECT COUNT(*) FROM %s WHERE %s IN "
                 "(SELECT entrez FROM genes WHERE species=?)" % (t, col))
            n = con.execute(q, (target,)).fetchone()[0]
            if n:
                plan.append((t, q.split("WHERE", 1)[1].strip(), (target,), n))
            break

# the uploads table keeps its own record
if "uploads" in tables:
    for col in ("upload_id", "id"):
        if col in columns("uploads"):
            n = con.execute("SELECT COUNT(*) FROM uploads WHERE %s=?" % col,
                            (upload_id,)).fetchone()[0]
            if n:
                plan.append(("uploads", "%s=?" % col, (upload_id,), n))
            break

if not plan:
    print("Nothing found for that upload.")
    sys.exit(0)

print("Rows that would go:")
for t, where, args, n in plan:
    print("  %-22s %8s rows" % (t, "{:,}".format(n)))

if not a.yes:
    print("\nNothing deleted. Run again with --yes to delete.")
    sys.exit(0)

print("\nDeleting...")
for t, where, args, n in plan:
    con.execute("DELETE FROM %s WHERE %s" % (t, where), args)
    print("  %-22s done" % t)
con.commit()

left = [r[0] for r in con.execute(
    "SELECT DISTINCT species FROM transcripts ORDER BY species")]
print("\nOrganisms now: %s" % ", ".join(left))

if not a.no_vacuum:
    print("\nVACUUM - this takes a while and needs free disk...")
    before = os.path.getsize(DB)
    con.isolation_level = None
    con.execute("VACUUM")
    after = os.path.getsize(DB)
    print("done.\n\n%.2f GB -> %.2f GB" % (before / 1e9, after / 1e9))

con.close()
