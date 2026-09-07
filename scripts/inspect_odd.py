"""Show transcripts that fail the codon check, and those with no CDS."""
import sys
sys.path.insert(0, ".")
from src.mane import transcripts

odd, nocds = [], []
for r in transcripts():
    if r["cds_start"] is None:
        nocds.append(r)
    elif (r["cds_end"] - r["cds_start"] + 1) % 3:
        odd.append(r)

print("not divisible by 3:", len(odd))
for r in odd:
    print("  ", r["refseq"], r["symbol"], "CDS", r["cds_raw"],
          "length", r["cds_end"] - r["cds_start"] + 1)

print("no CDS:", len(nocds))
for r in nocds[:10]:
    print("  ", r["refseq"], r["symbol"])
