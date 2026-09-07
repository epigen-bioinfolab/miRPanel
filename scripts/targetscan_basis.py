"""Which miRBase release is TargetScan v8.0 built on? Compare its seeds to R22 and R23."""
import csv

TS = "data/raw/miR_Family_Info.txt"

def seed_of(seq):
    """Seed = positions 2-8, in DNA letters."""
    return seq.upper().replace("U", "T")[1:8]

def fasta_seeds(path, prefix="hsa-"):
    """Return {accession: seed} for one species from a miRBase mature.fa."""
    out, acc, parts = {}, None, []
    for line in open(path):
        line = line.strip()
        if line.startswith(">"):
            if acc:
                out[acc] = seed_of("".join(parts))
            f = line[1:].split()
            acc = f[1] if f[0].startswith(prefix) else None
            parts = []
        elif acc:
            parts.append(line)
    if acc:
        out[acc] = seed_of("".join(parts))
    return out

r22 = fasta_seeds("data/raw/mature_r22.fa")
r23 = fasta_seeds("data/raw/mature_r23.fa")
print("human accessions  R22:", len(r22), " R23:", len(r23))

rows = [r for r in csv.DictReader(open(TS), delimiter="\t")
        if r["Species ID"] == "9606"]

for label, ref in (("R22", r22), ("R23", r23)):
    same = diff = absent = 0
    for r in rows:
        acc = r["MiRBase Accession"].strip()
        ts = r["Seed+m8"].strip().upper().replace("U", "T")
        if acc not in ref:
            absent += 1
        elif ref[acc] == ts:
            same += 1
        else:
            diff += 1
    print(f"TargetScan vs {label}:  same {same}   different {diff}   absent {absent}")
