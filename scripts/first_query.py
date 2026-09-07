"""First real end-to-end query: which human genes does one miRNA target?"""
import sys, time
from collections import Counter
sys.path.insert(0, ".")
from src.db import connect
from src.tools.seed import get_6mer_site, find_all, classify_site

QUERY = "hsa-miR-21-5p"

con = connect()
row = con.execute("""SELECT m.accession, m.name, m.sequence, m.seed
                     FROM mirna_aliases a JOIN mirnas m ON a.accession = m.accession
                     WHERE a.alias = ?""", (QUERY,)).fetchone()
acc, name, seq, seed = row
print("resolved %s -> %s  (%s)" % (QUERY, acc, name))
print("  sequence %s" % seq)
print("  seed     %s   target site %s" % (seed, get_6mer_site(seq)))

tx = con.execute("""SELECT refseq, symbol, length, cds_start, cds_end, sequence
                    FROM transcripts WHERE species = 'human'""").fetchall()
print("  scanning %d transcripts" % len(tx))


def region_of(pos, cds_start, cds_end):
    if cds_start is None:
        return "ncRNA"
    if pos < cds_start:
        return "5UTR"
    if pos <= cds_end:
        return "CDS"
    return "3UTR"


site = get_6mer_site(seq)
t0 = time.time()
hits = []
for refseq, symbol, length, cs, ce, s in tx:
    for p in find_all(site, s):
        kind = classify_site(seq, s, p)
        if kind == "6mer":
            continue
        hits.append((symbol, refseq, region_of(p + 1, cs, ce), kind, p + 1))
print("\n%d sites (7mer and better) in %.2f s" % (len(hits), time.time() - t0))
print("  genes hit:", len(set(h[0] for h in hits)))
print("  by region:", dict(Counter(h[2] for h in hits)))
print("  by site:  ", dict(Counter(h[3] for h in hits)))

print("\nPDCD4 - a known validated miR-21 target:")
found = [h for h in hits if h[0] == "PDCD4"]
for h in found:
    print("   %s  %s  %s  position %d" % (h[1], h[2], h[3], h[4]))
if not found:
    print("   none found")

print("\n8mer sites in 3'UTRs, first 10 genes:")
for h in [x for x in hits if x[3] == "8mer" and x[2] == "3UTR"][:10]:
    print("   %-12s %s  position %d" % (h[0], h[1], h[4]))
con.close()
