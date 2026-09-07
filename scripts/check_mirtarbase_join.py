"""How well do miRTarBase names and Entrez ids join to our tables?"""
import csv, sqlite3

DB = "data/processed/mirna.db"

def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)

def ent(x):
    """'6541.0' -> '6541'; blank -> None."""
    x = x.strip()
    if not x:
        return None
    return x.split(".")[0]

con = sqlite3.connect(DB)
by_name = {n: a for n, a in con.execute("SELECT name, accession FROM mirnas WHERE species='hsa'")}
by_alias = {a: acc for a, acc in con.execute("SELECT alias, accession FROM mirna_aliases")}
genes = {e for (e,) in con.execute("SELECT entrez FROM genes")}

def check(path, label):
    n = nm = al = miss = ge = gmiss = 0
    misses = set()
    for r in rows(path):
        if r["Species (miRNA)"] != "hsa":
            continue
        n += 1
        m = r["miRNA"].strip()
        if m in by_name:
            nm += 1
        elif m in by_alias:
            al += 1
        else:
            miss += 1
            if len(misses) < 5:
                misses.add(m)
        e = ent(r["Target Gene (Entrez ID)"])
        if e in genes:
            ge += 1
        else:
            gmiss += 1
    print(label, "rows", n)
    print("  miRNA by current name:", nm)
    print("  miRNA by alias       :", al)
    print("  miRNA unresolved     :", miss, sorted(misses))
    print("  gene resolved        :", ge)
    print("  gene unresolved      :", gmiss)
    print()

check("data/raw/mirtarbase_SE_WR.csv", "SE_WR")
check("data/raw/mirtarbase_target_sites.csv", "TARGET_SITES")
