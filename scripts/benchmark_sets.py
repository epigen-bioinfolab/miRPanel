"""Build the positive and negative gene sets for the benchmark.

    python scripts/benchmark_sets.py [--n-mirnas 8] [--min 60] [--ratio 3]
                                     [--tolerance 0.15] [--rng 1]

Writes data/tmp/benchmark_sets.json and prints what it built. Runs no tools:
this only decides which genes are being asked about, which is the part that
decides whether the benchmark means anything.

POSITIVES
  miRTarBase pairs with strong-method evidence (reporter assay, western blot,
  qPCR) reported as functional, restricted to genes with a MANE Select
  transcript because that is what the tools scan. A positive the tool could
  never have found is not a fair test.

  This excludes miRTarBase itself from being benchmarked: it would be scoring
  its own answer key.

NEGATIVES  -  two sets, on purpose
  Neither is a true negative. No such thing exists here: a gene nobody has
  reported is not a gene that is not targeted. Both sets exclude every gene
  with ANY reported interaction with that miRNA, strong or weak, functional
  or not - a gene with weak evidence is not safe to call a non-target.

  matched   same 3'UTR length as the positive it replaces, within a
            tolerance. Real targets have longer 3'UTRs (median 1,626 nt for
            miR-21's validated targets against 1,083 nt genome-wide), so
            without matching every tool scores well partly by preferring long
            UTRs, and the benchmark measures UTR length instead of targeting.
  random    every gene with no reported interaction, not a sample of them.
            The tools run transcriptome-wide regardless, so there is no cost
            to scoring all ~18,000 and no sampling noise in the resulting
            false-positive rate.

  Running both is the point: the gap between them measures the size of the
  confound rather than asserting it.

SEED REDUNDANCY
  Every tool here works from the seed, so two miRNAs sharing one are close to
  the same test twice. miR-29a/29b, miR-17/20a and miR-200b/200c are each one
  seed. The chooser keeps one miRNA per seed and says which it dropped.
"""
import argparse
import json
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, "src")
import db

ap = argparse.ArgumentParser()
ap.add_argument("--n-mirnas", type=int, default=8)
ap.add_argument("--min", type=int, default=60,
                help="fewest positives for a miRNA to be included")
ap.add_argument("--ratio", type=int, default=3,
                help="matched negatives per positive")
ap.add_argument("--tolerance", type=float, default=0.15,
                help="matched negative's 3'UTR within this fraction")
ap.add_argument("--rng", type=int, default=1)
a = ap.parse_args()

con = db.connect()
rng = random.Random(a.rng)
OUT = os.path.join("data", "tmp", "benchmark_sets.json")

# ---------------------------------------------------------------- the pool
mane = {r[0] for r in con.execute(
    "SELECT DISTINCT entrez FROM transcripts WHERE mane_status='MANE Select'")}

utr = {}
for entrez, length in con.execute(
        "SELECT x.entrez, r.length FROM regions r "
        "JOIN transcripts x ON x.refseq = r.refseq "
        "WHERE r.region='3UTR' AND x.mane_status='MANE Select'"):
    utr[entrez] = length
for g in mane:                      # a MANE transcript can have no 3'UTR
    utr.setdefault(g, 0)

# ------------------------------------------------------ choose the miRNAs
cand = con.execute("""
    SELECT m.name, m.accession, m.seed, COUNT(DISTINCT t.entrez) AS n
    FROM mirtarbase t
    JOIN mirnas m ON m.accession = t.accession
    JOIN transcripts x ON x.entrez = t.entrez
                      AND x.mane_status = 'MANE Select'
    WHERE t.n_strong_func > 0 AND m.species = 'hsa'
    GROUP BY m.accession HAVING n >= ? ORDER BY n DESC
""", (a.min,)).fetchall()

chosen, seen_seed, dropped = [], {}, []
for name, acc, seed, n in cand:
    if seed in seen_seed:
        dropped.append((name, seed, seen_seed[seed]))
        continue
    seen_seed[seed] = name
    chosen.append({"name": name, "accession": acc, "seed": seed, "n": n})
    if len(chosen) == a.n_mirnas:
        break

print("%d miRNAs, one per seed:\n" % len(chosen))
print("%-20s %-14s %-10s %s" % ("miRNA", "accession", "seed", "positives"))
for c in chosen:
    print("%-20s %-14s %-10s %d" % (c["name"], c["accession"], c["seed"],
                                    c["n"]))
if dropped:
    print("\ndropped for sharing a seed with one already chosen:")
    for name, seed, kept in dropped:
        print("   %-20s %-10s same seed as %s" % (name, seed, kept))
    print("   (every tool here works from the seed, so these would have been")
    print("    close to the same test run twice)")

# --------------------------------------------------------- build the sets
def matched(pos_genes, pool):
    """A negative of similar 3'UTR length for each positive, no repeats."""
    by_len = sorted(pool, key=lambda g: utr[g])
    lens = [utr[g] for g in by_len]
    used, out, misses = set(), [], 0
    import bisect
    for p in pos_genes:
        target = utr[p]
        lo, hi = target * (1 - a.tolerance), target * (1 + a.tolerance)
        i, j = bisect.bisect_left(lens, lo), bisect.bisect_right(lens, hi)
        window = [g for g in by_len[i:j] if g not in used]
        if not window:               # widen rather than silently drop
            misses += 1
            window = [g for g in by_len if g not in used]
            window.sort(key=lambda g: abs(utr[g] - target))
            window = window[:50]
        if not window:
            continue
        pick = rng.choice(window)
        used.add(pick)
        out.append(pick)
    return out, misses


sets, summary = {}, []
for c in chosen:
    acc = c["accession"]
    pos = sorted({r[0] for r in con.execute(
        "SELECT DISTINCT entrez FROM mirtarbase WHERE accession=? "
        "AND n_strong_func > 0", (acc,))} & mane)
    # anything reported at all is unsafe as a negative
    reported = {r[0] for r in con.execute(
        "SELECT DISTINCT entrez FROM mirtarbase WHERE accession=?", (acc,))}
    reported |= {r[0] for r in con.execute(
        "SELECT DISTINCT entrez FROM mirtarbase_evidence WHERE accession=? "
        "AND entrez IS NOT NULL", (acc,))}
    pool = sorted(mane - reported)

    m_neg, misses = [], 0
    for _ in range(a.ratio):
        got, miss = matched(pos, [g for g in pool if g not in set(m_neg)])
        m_neg += got
        misses += miss

    # The unmatched set is every gene with no reported interaction, not a
    # sample of them. The tools run transcriptome-wide anyway, so scoring
    # 18,000 genes costs nothing extra - and a sample of ~100 gave median
    # 3'UTR lengths ranging 648-1,471 nt across eight miRNAs, which is
    # sampling noise that would have gone straight into the false-positive
    # rate.
    r_neg = pool

    sets[acc] = {"name": c["name"], "seed": c["seed"], "positives": pos,
                 "negatives_matched": m_neg, "negatives_random": r_neg}

    def med(gs):
        v = sorted(utr[g] for g in gs)
        return v[len(v) // 2] if v else 0
    summary.append((c["name"], len(pos), len(m_neg), len(r_neg), med(pos),
                    med(m_neg), med(r_neg), misses))

print("\n3'UTR medians - the matched set should track the positives, the "
      "random set should not\n")
print("%-20s %5s %6s %7s %8s %8s %8s %s"
      % ("miRNA", "pos", "match", "random", "pos nt", "matched", "random",
         "widened"))
for name, npos, nneg, nrand, mp, mm, mr, miss in summary:
    print("%-20s %5d %6d %7d %8d %8d %8d %d"
          % (name, npos, nneg, nrand, mp, mm, mr, miss))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"rng": a.rng, "ratio": a.ratio, "tolerance": a.tolerance,
           "min_positives": a.min, "sets": sets},
          open(OUT, "w"), indent=1)
print("\nwrote %s" % OUT)
print("rng seed %d recorded in the file, so this is reproducible exactly."
      % a.rng)
