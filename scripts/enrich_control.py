"""Does the seed filter add anything, or does it only make the list smaller?

    python scripts/enrich_control.py <job_id> [--repeats 3]

TargetScan-conserved alone gave stronger enrichment than 8mer-and-conserved.
That could mean the seed filter is useless, or simply that 150 genes have less
statistical power than 381. This separates the two: it enriches the real
intersection, then random samples of the SAME SIZE drawn from the same
conserved genes. If the real one is not better than the random ones, the seed
filter is adding nothing but attrition.
"""
import argparse
import os
import random
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
ap.add_argument("--repeats", type=int, default=3)
ap.add_argument("--seed-rng", type=int, default=1)
a = ap.parse_args()

con = db.connect()
conserved = geneset.select(con, a.job, {"targetscan": "conserved"})["genes"]
both = geneset.select(con, a.job, {"seed": "8mer", "targetscan": "conserved"})["genes"]
background = [r[0] for r in con.execute(
    "SELECT DISTINCT entrez FROM transcripts WHERE mane_status='MANE Select'")]

print("conserved            %d genes" % len(conserved))
print("8mer AND conserved   %d genes" % len(both))
print("background           %d genes\n" % len(background))
if not both or len(both) >= len(conserved):
    sys.exit("nothing to compare")

os.makedirs(TMP, exist_ok=True)
bpath = os.path.join(TMP, "control_background.txt")
open(bpath, "w").write("\n".join(str(g) for g in background) + "\n")


def enrich(genes, tag):
    gpath = os.path.join(TMP, "control_%s_genes.txt" % tag)
    opath = os.path.join(TMP, "control_%s.tsv" % tag)
    open(gpath, "w").write("\n".join(str(g) for g in genes) + "\n")
    subprocess.run(["Rscript", RSCRIPT, gpath, bpath, opath],
                   capture_output=True, text=True)
    rows = [l.rstrip("\n").split("\t") for l in open(opath)][1:]
    if not rows:
        return 0, None, None
    head = open(opath).readline().rstrip("\n").split("\t")
    padj = head.index("p_adjust")
    desc = head.index("description")
    best = min(rows, key=lambda r: float(r[padj]))
    return len(rows), float(best[padj]), best[desc]


n, p, term = enrich(both, "real")
print("REAL   8mer AND conserved, %d genes" % len(both))
print("       %d terms, best adjusted p %.2e  (%s)\n" % (n, p or 1, term or "-"))

rng = random.Random(a.seed_rng)
print("RANDOM %d genes drawn from the %d conserved genes, %d times"
      % (len(both), len(conserved), a.repeats))
beats = 0
for i in range(a.repeats):
    sample = rng.sample(conserved, len(both))
    rn, rp, rterm = enrich(sample, "rand%d" % i)
    print("       run %d: %d terms, best adjusted p %.2e  (%s)"
          % (i + 1, rn, rp or 1, rterm or "-"))
    if n > rn:
        beats += 1

print("\nthe real list produced more terms than %d of %d random lists of the "
      "same size" % (beats, a.repeats))
print("if that is not most of them, the seed filter is not selecting biology,")
print("it is only making the list smaller.")
