"""Which miRNAs have enough strong experimental evidence to benchmark against?

    python scripts/benchmark_candidates.py [--min 30] [--top 25]

A benchmark needs positives, and the only positives available are miRTarBase
pairs supported by a strong method (reporter assay, western blot, qPCR) and
reported as functional. This counts them per miRNA so the benchmark set is
chosen from what the data actually supports rather than from which miRNAs are
famous.

Two restrictions, both deliberate:
  - only genes with a MANE Select transcript, because that is what the tools
    scan; a positive the tool could never have found is not a fair test
  - only miRNAs present in miRBase 23 under an accession, since that is how
    every job is keyed

It also reports the 3'UTR length of the positives against every gene, because
the benchmark's negatives have to be matched on that and it is worth seeing
the size of the bias before designing around it.
"""
import argparse
import statistics
import sys

sys.path.insert(0, "src")
import db

ap = argparse.ArgumentParser()
ap.add_argument("--min", type=int, default=30,
                help="fewest strong functional targets to be worth including")
ap.add_argument("--top", type=int, default=25)
a = ap.parse_args()

con = db.connect()

rows = con.execute("""
    SELECT m.name, m.accession, COUNT(DISTINCT t.entrez) AS n
    FROM mirtarbase t
    JOIN mirnas m ON m.accession = t.accession
    JOIN transcripts x ON x.entrez = t.entrez
                      AND x.mane_status = 'MANE Select'
    WHERE t.n_strong_func > 0 AND m.species = 'hsa'
    GROUP BY m.accession
    HAVING n >= ?
    ORDER BY n DESC
    LIMIT ?
""", (a.min, a.top)).fetchall()

print("miRNAs with at least %d strong functional targets on a MANE Select "
      "gene\n" % a.min)
print("%-22s %-14s %s" % ("miRNA", "accession", "targets"))
for name, acc, n in rows:
    print("%-22s %-14s %d" % (name, acc, n))
print("\n%d miRNAs qualify at this threshold." % len(rows))

# --- how strong is the 3'UTR length bias we have to match away?
def utrs(entrez_list=None):
    q = ("SELECT r.length FROM regions r "
         "JOIN transcripts x ON x.refseq = r.refseq "
         "WHERE r.region='3UTR' AND x.mane_status='MANE Select'")
    args = []
    if entrez_list:
        q += " AND x.entrez IN (%s)" % ",".join("?" * len(entrez_list))
        args = list(entrez_list)
    return [r[0] for r in con.execute(q, args)]


allutr = utrs()
print("\n3'UTR length, every MANE Select gene: median %d nt (n=%d)"
      % (statistics.median(allutr), len(allutr)))

if rows:
    top = rows[0]
    pos = [r[0] for r in con.execute(
        "SELECT DISTINCT entrez FROM mirtarbase WHERE accession=? "
        "AND n_strong_func > 0", (top[1],))]
    putr = utrs(pos)
    if putr:
        print("3'UTR length, %s strong targets:  median %d nt (n=%d)"
              % (top[0], statistics.median(putr), len(putr)))
        print("\nIf the second median is clearly larger, unmatched negatives "
              "would let every\ntool score well merely by preferring long "
              "3'UTRs. That is the confound the\nmatched draw removes, and "
              "the reason for running both.")
