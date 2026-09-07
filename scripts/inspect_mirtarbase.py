"""Summarise the miRTarBase files we downloaded."""
import csv, collections

def rows(path):
    """Yield dict rows; utf-8-sig strips the byte-order mark from the header."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)

def summarise(path, label):
    n = hum = 0
    sup, exp = collections.Counter(), collections.Counter()
    for r in rows(path):
        n += 1
        if r["Species (miRNA)"] != "hsa":
            continue
        hum += 1
        sup[r["Support Type"]] += 1
        for e in r["Experiments"].split("//"):
            exp[e.strip()] += 1
    print(label, " total", n, " human", hum)
    for k, v in sup.most_common():
        print("   support   :", k, v)
    for k, v in exp.most_common(8):
        print("   experiment:", k, v)
    print()

summarise("data/raw/mirtarbase_SE_WR.csv", "SE_WR")
summarise("data/raw/mirtarbase_target_sites.csv", "TARGET_SITES")

for r in rows("data/raw/mirtarbase_target_sites.csv"):
    if r["Species (miRNA)"] == "hsa":
        print("example target-site row:")
        for k, v in r.items():
            print("   ", k, "=", v[:70])
        break
