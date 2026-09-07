"""Do two transcripts of the same gene both appear in Summary_Counts?"""
import csv, sys

def base(x):
    return x.split(".")[0]

ens = {}
for r in csv.DictReader(open("data/raw/Gene_info.txt"), delimiter="\t"):
    if r["Species ID"] == "9606":
        ens[base(r["Transcript ID"])] = base(r["Gene ID"])

seen = {}
with open(sys.argv[1] if len(sys.argv) > 1 else "data/raw/Summary_Counts.default_predictions.txt") as fh:
    next(fh)
    for line in fh:
        f = line.split("\t")
        if f[3] != "9606":
            continue
        seen.setdefault(ens.get(base(f[0]), "?"), set()).add(base(f[0]))

multi = {g: t for g, t in seen.items() if g != "?" and len(t) > 1}
print("genes seen                  :", len(seen))
print("genes with >1 transcript    :", len(multi))
print("transcripts not in Gene_info:", len(seen.get("?", ())))
