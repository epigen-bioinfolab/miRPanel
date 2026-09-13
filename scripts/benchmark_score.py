"""Score the benchmark: how often is each tool right, and how often wrong?

    python scripts/benchmark_score.py [--out manifests/benchmark_raw.tsv]

Reads data/tmp/benchmark_sets.json (sets plus job ids) and, for every tool and
every threshold that tool offers, counts how many positives it called and how
many negatives it called.

WHAT IS REPORTED, AND WHY IN THIS ORDER
  recall  TP / positives                 does not depend on how many
  FPR     FP / negatives                 negatives we chose to include
  precision  TP / (TP + FP)              DOES depend on it, so it is always
                                         printed with the ratio it came from

At 1 positive to 3 negatives, a coin flip scores 0.25 precision. At 1 to 200
the same tool scores 0.015. Real prevalence is unknown, so no bare precision
figure from this benchmark means anything on its own.

TWO NEGATIVE SETS
  matched    3'UTR length matched to the positives
  unmatched  every gene with no reported interaction (~18,000)
The gap between their FPRs measures how much of a tool's apparent accuracy is
really just a preference for long 3'UTRs.

miRTarBase is not scored. The positives are miRTarBase strong-evidence pairs,
so it would be marking its own answer key.

LIMITATION, stated once and carried into every table that uses these numbers:
there are no true negatives here. A gene nobody has reported is not a gene
that is not targeted, so "false positive" means PREDICTED BUT NOT REPORTED -
partly a statement about how much attention a gene has received.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, "src")
import db

SETS = os.path.join("data", "tmp", "benchmark_sets.json")

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.path.join("manifests", "benchmark_raw.tsv"))
a = ap.parse_args()

if not os.path.exists(SETS):
    sys.exit("no %s - run scripts/benchmark_sets.py first" % SETS)
data = json.load(open(SETS))
con = db.connect()

# Each rule is (tool, label, SQL predicate) - the gene is "called" if the job
# holds at least one row for it matching the predicate.
RULES = [
    ("seed", "8mer only", "tool='seed' AND site_type='8mer'"),
    ("seed", "7mer or better",
     "tool='seed' AND site_type IN ('8mer','7mer-m8','7mer-A1')"),
    ("seed", "any site incl 6mer", "tool='seed'"),
    ("targetscan", "any prediction", "tool='targetscan'"),
    ("targetscan", "conserved site", "tool='targetscan' AND low_confidence=0"),
    ("targetscan", "context++ <= -0.3",
     "tool='targetscan' AND score <= -0.3"),
    ("rnahybrid", "dG <= -20", "tool='rnahybrid' AND score <= -20"),
    ("rnahybrid", "dG <= -25", "tool='rnahybrid' AND score <= -25"),
    ("rnahybrid", "dG <= -30", "tool='rnahybrid' AND score <= -30"),
]


def called(job_id, predicate):
    """Every gene this job called under this rule."""
    return {r[0] for r in con.execute(
        "SELECT DISTINCT entrez FROM results WHERE job_id=? AND " + predicate,
        (job_id,))}


rows = []
missing = []
for acc, s in data["sets"].items():
    job = s.get("job_id")
    if not job:
        missing.append(s["name"])
        continue
    st = con.execute("SELECT status FROM jobs WHERE job_id=?", (job,)).fetchone()
    if not st or st[0] != "done":
        missing.append("%s (%s)" % (s["name"], st[0] if st else "no such job"))
        continue
    pos = set(s["positives"])
    negm = set(s["negatives_matched"])
    negr = set(s["negatives_random"])
    for tool, label, pred in RULES:
        hit = called(job, pred)
        tp = len(hit & pos)
        fpm = len(hit & negm)
        fpr_ = len(hit & negr)
        rows.append({
            "mirna": s["name"], "tool": tool, "rule": label,
            "n_pos": len(pos), "tp": tp,
            "recall": tp / len(pos) if pos else 0.0,
            "n_neg_matched": len(negm), "fp_matched": fpm,
            "fpr_matched": fpm / len(negm) if negm else 0.0,
            "n_neg_unmatched": len(negr), "fp_unmatched": fpr_,
            "fpr_unmatched": fpr_ / len(negr) if negr else 0.0,
        })

if missing:
    print("not scored, job not finished: %s\n" % ", ".join(missing))
if not rows:
    sys.exit("nothing to score yet - let the worker finish")

# ---------------------------------------------------------------- pooled
print("POOLED OVER %d miRNA(s) - every positive and negative counted once\n"
      % len({r["mirna"] for r in rows}))
print("%-12s %-20s %7s %8s %10s %12s"
      % ("tool", "rule", "recall", "FPR", "FPR", "precision"))
print("%-12s %-20s %7s %8s %10s %12s"
      % ("", "", "", "matched", "unmatched", "at 1:3 matched"))

pooled = {}
for r in rows:
    k = (r["tool"], r["rule"])
    p = pooled.setdefault(k, dict.fromkeys(
        ("tp", "n_pos", "fp_matched", "n_neg_matched",
         "fp_unmatched", "n_neg_unmatched"), 0))
    for f in p:
        p[f] += r[f]

order = [(t, l) for t, l, _ in RULES]
for k in order:
    p = pooled.get(k)
    if not p:
        continue
    rec = p["tp"] / p["n_pos"] if p["n_pos"] else 0
    fm = p["fp_matched"] / p["n_neg_matched"] if p["n_neg_matched"] else 0
    fu = p["fp_unmatched"] / p["n_neg_unmatched"] if p["n_neg_unmatched"] else 0
    prec = p["tp"] / (p["tp"] + p["fp_matched"]) if (p["tp"] + p["fp_matched"]) else 0
    print("%-12s %-20s %7.3f %8.3f %10.3f %12.3f"
          % (k[0], k[1], rec, fm, fu, prec))

print("\nrecall and FPR are properties of the tool.")
print("precision depends on the 1:3 ratio above and means nothing without it.")
print("\nthe two FPR columns differ only because of 3'UTR length: the gap is")
print("how much of a tool's apparent accuracy is a preference for long UTRs.")

# ---------------------------------------------------------- per miRNA
print("\n\nPER miRNA, recall\n")
mirnas = sorted({r["mirna"] for r in rows})
print("%-12s %-20s %s" % ("tool", "rule",
                          " ".join("%9s" % m.replace("hsa-", "")[:9]
                                   for m in mirnas)))
for k in order:
    line = []
    for m in mirnas:
        hit = [r for r in rows if r["mirna"] == m and (r["tool"], r["rule"]) == k]
        line.append("%9.3f" % hit[0]["recall"] if hit else "%9s" % "-")
    if any(x.strip() != "-" for x in line):
        print("%-12s %-20s %s" % (k[0], k[1], " ".join(line)))

# ---------------------------------------------------------------- write
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
cols = ["mirna", "tool", "rule", "n_pos", "tp", "recall", "n_neg_matched",
        "fp_matched", "fpr_matched", "n_neg_unmatched", "fp_unmatched",
        "fpr_unmatched"]
with open(a.out, "w") as fh:
    fh.write("\t".join(cols) + "\n")
    for r in rows:
        fh.write("\t".join(str(r[c]) for c in cols) + "\n")
print("\n\nwrote %s (%d rows)" % (a.out, len(rows)))
