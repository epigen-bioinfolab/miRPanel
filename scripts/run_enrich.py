"""Run GO and KEGG enrichment on the genes a filter selects.

    python scripts/run_enrich.py <job_id> [--seed 8mer] [--targetscan conserved]
                                 [--rnahybrid -25] [--mirtarbase strong]
                                 [--regions 5UTR,CDS,3UTR] [--match all|any]

Writes data/tmp/enrich_<job>.tsv and prints the top terms. The gene list and
the background are both written out beside it, so any result can be traced
back to exactly which genes produced it.
"""
import argparse
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, "src")
import db
import geneset

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RSCRIPT = os.path.join(HERE, "R", "enrich.R")
TMP = os.path.join(HERE, "data", "tmp")

ap = argparse.ArgumentParser()
ap.add_argument("job")
ap.add_argument("--seed", default="8mer",
                help="site type, or 'none' to leave the seed box unticked")
ap.add_argument("--targetscan")
ap.add_argument("--rnahybrid")
ap.add_argument("--mirtarbase")
ap.add_argument("--regions")
ap.add_argument("--match", default="all", choices=("all", "any"))
a = ap.parse_args()

con = db.connect()
spec = {"seed": None if a.seed in ("none", "") else a.seed,
        "targetscan": a.targetscan, "rnahybrid": a.rnahybrid,
        "mirtarbase": a.mirtarbase, "match": a.match,
        "regions": a.regions.split(",") if a.regions else None}
sel = geneset.select(con, a.job, spec)
if not sel["count"]:
    sys.exit("no genes selected - nothing to test")

# Background A: every gene the tool could have scanned.
background = [r[0] for r in con.execute(
    "SELECT DISTINCT entrez FROM transcripts WHERE mane_status='MANE Select'")]

os.makedirs(TMP, exist_ok=True)
# the filter is part of the name, so two filters never overwrite each other
tag = "%s_%s" % (a.job, hashlib.sha1(
    repr(sorted((k, str(v)) for k, v in spec.items())).encode()).hexdigest()[:6])
gpath = os.path.join(TMP, "enrich_%s_genes.txt" % tag)
bpath = os.path.join(TMP, "enrich_%s_background.txt" % tag)
opath = os.path.join(TMP, "enrich_%s.tsv" % tag)
open(gpath, "w").write("\n".join(str(g) for g in sel["genes"]) + "\n")
open(bpath, "w").write("\n".join(str(g) for g in background) + "\n")

print(sel["sentence"])
print("background: %d genes (every MANE Select gene)\n" % len(background))

p = subprocess.run(["Rscript", RSCRIPT, gpath, bpath, opath], text=True)
if p.returncode != 0:
    sys.exit("Rscript failed with code %d" % p.returncode)

print("\nwrote %s" % opath)
print("gene list %s\nbackground %s" % (gpath, bpath))
