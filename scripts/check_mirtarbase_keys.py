"""What combination of columns is unique in the miRTarBase files?"""
import csv, collections

def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)

def keys(path, label):
    n = 0
    ids, pairs, k2, k3 = set(), set(), collections.Counter(), collections.Counter()
    for r in rows(path):
        if r["Species (miRNA)"] != "hsa":
            continue
        n += 1
        ids.add(r["miRTarBase ID"])
        pairs.add((r["miRNA"], r["Target Gene (Entrez ID)"]))
        k2[(r["miRTarBase ID"], r["References (PMID)"])] += 1
        k3[(r["miRTarBase ID"], r["References (PMID)"], r.get("Target Site", ""))] += 1
    print(label, "human rows", n)
    print("  distinct MIRT ids        ", len(ids))
    print("  distinct (miRNA, entrez) ", len(pairs))
    print("  dup (id, pmid)           ", sum(1 for v in k2.values() if v > 1))
    print("  dup (id, pmid, site)     ", sum(1 for v in k3.values() if v > 1))
    print()

keys("data/raw/mirtarbase_SE_WR.csv", "SE_WR")
keys("data/raw/mirtarbase_target_sites.csv", "TARGET_SITES")
