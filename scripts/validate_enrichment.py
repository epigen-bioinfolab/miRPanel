"""Does the database say exactly what R said?

    python scripts/validate_enrichment.py <run_id> [--against old.tsv]

Two different claims, checked separately, because they can fail for different
reasons and only one of them is a bug:

  A. FAITHFULNESS - the database matches the TSV this very run produced.
     Every term, every number, every gene list. This must be exact. Anything
     else means the storage layer corrupted a result on the way in.

  B. REPRODUCIBILITY - this run matches an earlier, independent run of the
     same filter. GO must match: it comes from a fixed annotation package.
     KEGG is fetched live from the KEGG server, so a difference there is
     news about KEGG, not a defect in this tool - it is reported, not failed.

It also recomputes every p-value from the four integers the database stores,
using nothing but the standard library. If those agree, the stored numbers
are self-sufficient: the science survives without R, without clusterProfiler,
and without an internet connection.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, "src")
import db
import enrichment as E

ap = argparse.ArgumentParser()
ap.add_argument("run_id")
ap.add_argument("--against", help="an earlier TSV of the same filter")
a = ap.parse_args()

con = db.connect()
run = E.get_run(con, a.run_id)
if not run:
    sys.exit("no such run: %s" % a.run_id)
print("%s  %s" % (a.run_id, run["rule_sentence"]))
if run["status"] != "done":
    # Not a failure. A run that has not finished has nothing to validate, and
    # printing FAIL for it would teach the reader to ignore a real FAIL.
    print("status is '%s' - nothing to check yet." % run["status"])
    if run["status"] == "failed":
        print("error: %s" % run["error"])
        sys.exit(1)
    print("wait for the worker to finish, then run this again.")
    sys.exit(0)
rows = E.terms(con, a.run_id)
print("%d genes (%s recognised by the annotation), %d terms, status %s\n"
      % (run["n_genes"], run["n_genes_annotated"], len(rows), run["status"]))

fails = []


def check(name, ok, detail=""):
    print("  %-46s %s%s" % (name, "PASS" if ok else "FAIL",
                            "" if ok else "  " + detail))
    if not ok:
        fails.append(name)


def read_tsv(path):
    lines = open(path).read().splitlines()
    head = lines[0].split("\t")
    out = {}
    for ln in lines[1:]:
        f = dict(zip(head, ln.split("\t")))
        k, n = (int(x) for x in f["gene_ratio"].split("/"))
        K, N = (int(x) for x in f["bg_ratio"].split("/"))
        out[(f["source"], f["term_id"])] = {
            "description": f["description"], "k": k, "n": n, "K": K, "N": N,
            "p_value": float(f["p_value"]), "p_adjust": float(f["p_adjust"]),
            "genes": f["genes"]}
    return out


def compare(db_rows, tsv, label, strict_sources=None):
    """strict_sources=None means every source must match."""
    d = {(r["source"], r["term_id"]): r for r in db_rows}
    keys_db = {k for k in d if strict_sources is None or k[0] in strict_sources}
    keys_ts = {k for k in tsv if strict_sources is None or k[0] in strict_sources}
    check("%s: same set of terms (%d)" % (label, len(keys_ts)),
          keys_db == keys_ts,
          "only in db: %s | only in file: %s"
          % (sorted(keys_db - keys_ts)[:3], sorted(keys_ts - keys_db)[:3]))

    bad = {"description": [], "k/n/K/N": [], "p_value": [], "p_adjust": [],
           "genes": []}
    for key in sorted(keys_db & keys_ts):
        r, t = d[key], tsv[key]
        if r["description"] != t["description"]:
            bad["description"].append(key)
        if (r["k_in_term_and_list"], r["n_in_list"],
                r["k_in_term_and_background"], r["n_in_background"]) != \
                (t["k"], t["n"], t["K"], t["N"]):
            bad["k/n/K/N"].append(key)
        if r["p_value"] != t["p_value"]:
            bad["p_value"].append(key)
        if r["p_adjust"] != t["p_adjust"]:
            bad["p_adjust"].append(key)
        if r["genes"] != t["genes"]:
            bad["genes"].append(key)
    for field, wrong in bad.items():
        check("%s: %s identical" % (label, field), not wrong,
              "%d differ, e.g. %s" % (len(wrong), wrong[:2]))


# ---- A. faithfulness: the database against this run's own output
own = os.path.join("data", "tmp", "%s.tsv" % a.run_id)
print("A. FAITHFULNESS - database against the TSV this run wrote")
if not os.path.exists(own):
    check("this run's TSV exists", False, own)
else:
    compare(rows, read_tsv(own), "own")
    meta = E._read_meta(os.path.join("data", "tmp", "%s_meta.tsv" % a.run_id))
    check("n_genes matches R", E._int(meta, "n_genes") == run["n_genes"])
    check("annotated count matches R",
          E._int(meta, "n_genes_annotated") == run["n_genes_annotated"])
    check("term count matches R", E._int(meta, "n_terms") == len(rows))

# ---- the four integers must reproduce the p-value on their own
print("\nB. SELF-SUFFICIENCY - p-values recomputed from the stored integers")


def logC(n, k):
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


worst, worst_term = 0.0, None
for r in rows:
    k, n = r["k_in_term_and_list"], r["n_in_list"]
    K, N = r["k_in_term_and_background"], r["n_in_background"]
    d = logC(N, n)
    mine = sum(math.exp(logC(K, i) + logC(N - K, n - i) - d)
               for i in range(k, min(n, K) + 1))
    rel = abs(mine - r["p_value"]) / r["p_value"] if r["p_value"] else 0.0
    if rel > worst:
        worst, worst_term = rel, r["term_id"]
if not rows:
    print("  %-46s no terms - nothing to recompute" % "(skipped)")
else:
    check("every p-value recomputable (worst %.1e, %s)" % (worst, worst_term),
          worst < 1e-9)

# ---- do the symbols in the terms belong to the genes we said we tested?
# Informational, not pass/fail. clusterProfiler names genes using
# org.Hs.eg.db's symbols and we store NCBI's; the two are built from the same
# source at different dates, so a handful of renamed genes can differ without
# anything being wrong. A large number would mean the wrong list was tested.
symbols = set()
for r in rows:
    symbols.update(r["genes"].split("/"))
tested = sorted(set(run["genes"]))
known = set()
for i in range(0, len(tested), 500):
    chunk = tested[i:i + 500]
    known.update(s for (s,) in con.execute(
        "SELECT DISTINCT symbol FROM genes WHERE entrez IN (%s)"
        % ",".join("?" * len(chunk)), chunk))
stray = sorted(symbols - known)
print("  %-46s %d of %d symbols%s"
      % ("gene names traced back to the tested list",
         len(symbols) - len(stray), len(symbols),
         "" if not stray else "  (differ: %s)" % stray[:6]))

# ---- C. reproducibility against an earlier independent run
if a.against:
    print("\nC. REPRODUCIBILITY - against %s" % a.against)
    old = read_tsv(a.against)
    go_only = {s for s in {k[0] for k in old} if s.startswith("GO")}
    compare(rows, old, "GO", strict_sources=go_only)
    new_k = {k for k in {(r["source"], r["term_id"]) for r in rows}
             if k[0] == "KEGG"}
    old_k = {k for k in old if k[0] == "KEGG"}
    print("  KEGG (live, not a pass/fail): %d then, %d now, %d in common"
          % (len(old_k), len(new_k), len(old_k & new_k)))
    if old_k != new_k:
        print("     KEGG's own pathway definitions changed between the two runs")

print("\n%s" % ("ALL CHECKS PASSED" if not fails
                else "%d FAILED: %s" % (len(fails), fails)))
sys.exit(1 if fails else 0)
