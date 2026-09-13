"""Are the four numbers behind each p-value recoverable, and do they mean
what they look like?

    python scripts/check_hypergeom.py data/tmp/enrich_<job>_<hash>.tsv

clusterProfiler prints GeneRatio "k/n" and BgRatio "K/N" and a p-value. If
those four integers really describe the test it ran, recomputing the p-value
from them must reproduce the one it printed. If it does, the database can
store the four numbers and anyone can redo the arithmetic in any language,
forever, without R, clusterProfiler, or an internet connection.

No scipy: the hypergeometric tail is done with log-gammas so this depends on
nothing but the standard library.
"""
import math
import sys

path = sys.argv[1]


def logC(n, k):
    """log of n-choose-k."""
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def p_over(k, n, K, N):
    """P(at least k of our n genes fall in a term that holds K of N).

    This is what an over-representation test asks. R computes it as
    phyper(k - 1, K, N - K, n, lower.tail = FALSE).
    """
    d = logC(N, n)
    return sum(math.exp(logC(K, i) + logC(N - K, n - i) - d)
               for i in range(k, min(n, K) + 1))


rows = [l.rstrip("\n").split("\t") for l in open(path)]
head, rows = rows[0], rows[1:]
c = {name: head.index(name) for name in head}
print("%d terms in %s\n" % (len(rows), path))

worst, worst_row = 0.0, None
bad_count = 0
denominators = {}

for r in rows:
    k, n = (int(x) for x in r[c["gene_ratio"]].split("/"))
    K, N = (int(x) for x in r[c["bg_ratio"]].split("/"))
    p = float(r[c["p_value"]])
    mine = p_over(k, n, K, N)
    rel = abs(mine - p) / p if p else 0.0
    if rel > worst:
        worst, worst_row = rel, (r[c["term_id"]], k, n, K, N, p, mine)

    # the genes column should hold exactly k symbols
    if len(r[c["genes"]].split("/")) != k:
        bad_count += 1

    denominators.setdefault(r[c["source"]], set()).add((n, N))

print("denominators, per ontology  (n = your genes annotated there, "
      "N = background annotated there)")
for src in sorted(denominators):
    for n, N in sorted(denominators[src]):
        print("   %-7s n = %-6d N = %d" % (src, n, N))

print("\ngene lists that did not hold exactly k symbols: %d" % bad_count)
print("worst relative difference between R's p-value and mine: %.2e" % worst)
if worst_row:
    t, k, n, K, N, p, mine = worst_row
    print("   %s  k=%d n=%d K=%d N=%d" % (t, k, n, K, N))
    print("   R: %.10e   recomputed: %.10e" % (p, mine))
print("\nanything below about 1e-9 means the four integers fully describe the")
print("test and the p-value never needs R again.")
