"""Is 3'UTR enrichment biology, or base composition? Compare real seeds to shuffled ones."""
import random, sys
from statistics import median
sys.path.insert(0, ".")
from src.db import connect
from src.tools.seed import get_6mer_site, find_all

random.seed(42)
GAP = "N" * 10          # separator so no pattern spans two genes
con = connect()

parts = {"3UTR": [], "CDS": [], "5UTR": []}
for length, cs, ce, seq in con.execute(
        "SELECT length, cds_start, cds_end, sequence FROM transcripts WHERE cds_start IS NOT NULL"):
    if cs > 1:
        parts["5UTR"].append(seq[:cs - 1])
    parts["CDS"].append(seq[cs - 1:ce])
    if ce < length:
        parts["3UTR"].append(seq[ce:])

pool = {k: GAP.join(v) for k, v in parts.items()}
del parts
for k, v in pool.items():
    print("%-6s %10.1f kb" % (k, len(v) / 1000))


def density(pattern):
    """Sites per kb in each region."""
    return {k: 1000.0 * len(find_all(pattern, v)) / len(v) for k, v in pool.items()}


def shuffle(s):
    letters = list(s)
    random.shuffle(letters)
    return "".join(letters)


seqs = [r[0] for r in con.execute(
    "SELECT sequence FROM mirnas WHERE species='human' ORDER BY accession LIMIT 100")]
sites = [get_6mer_site(s) for s in seqs]
sites = [s for s in sites if set(s) <= set("ACGT")]
print("\nreal seed sites:", len(sites))


def summarise(label, patterns):
    d3, dc, d5, ratios = [], [], [], []
    for p in patterns:
        d = density(p)
        d3.append(d["3UTR"]); dc.append(d["CDS"]); d5.append(d["5UTR"])
        if d["CDS"] > 0:
            ratios.append(d["3UTR"] / d["CDS"])
    print("\n%s  (n=%d)" % (label, len(patterns)))
    print("  median 3'UTR density  %.3f per kb" % median(d3))
    print("  median CDS   density  %.3f per kb" % median(dc))
    print("  median 5'UTR density  %.3f per kb" % median(d5))
    print("  median 3'UTR : CDS    %.2fx" % median(ratios))
    return median(ratios)


real = summarise("REAL SEED SITES", sites)
ctrl = summarise("SHUFFLED CONTROLS", [shuffle(s) for s in sites])

print("\n" + "=" * 46)
print("real %.2fx   shuffled %.2fx" % (real, ctrl))
if real > ctrl * 1.3:
    print("=> real seeds are enriched in 3'UTRs BEYOND composition")
elif ctrl > real * 1.3:
    print("=> shuffled exceed real - unexpected, worth investigating")
else:
    print("=> the enrichment is explained by base composition alone")
con.close()
