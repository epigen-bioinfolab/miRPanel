"""Measure how TargetScan v8.0 joins to our miRBase R23 tables."""
import csv, sqlite3

TS = "data/raw/miR_Family_Info.txt"
DB = "data/processed/mirna.db"

def ts_human(path=TS):
    """Yield human (taxid 9606) rows of miR_Family_Info.txt as dicts."""
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["Species ID"] == "9606":
                yield row

con = sqlite3.connect(DB)
ours = {a: (n, s) for a, n, s in
        con.execute("SELECT accession, name, seed FROM mirnas WHERE species='hsa'")}
changed = {a for (a,) in
           con.execute("SELECT accession FROM mirnas WHERE seed_changed=1")}
our_seeds = {s for _, s in ours.values()}

rows = list(ts_human())
hit = miss = agree = differ = differ_changed = miss_seed_ok = 0
examples = []
for r in rows:
    acc = r["MiRBase Accession"].strip()
    seed = r["Seed+m8"].strip().upper().replace("U", "T")
    if acc not in ours:
        miss += 1
        miss_seed_ok += seed in our_seeds
        continue
    hit += 1
    if ours[acc][1] == seed:
        agree += 1
        continue
    differ += 1
    if acc in changed:
        differ_changed += 1
    elif len(examples) < 5:
        examples.append((r["MiRBase ID"], acc, seed, ours[acc][1]))

print("TargetScan human rows :", len(rows))
print("our human miRNAs      :", len(ours))
print("distinct TS families  :", len({r["miR family"] for r in rows}))
print()
print("JOIN BY ACCESSION")
print("  matched             ", hit)
print("  not in our table    ", miss)
print()
print("SEED AGREEMENT (matched only)")
print("  identical           ", agree)
print("  different           ", differ)
print("    explained by R23 seed change:", differ_changed)
print("    unexplained                 :", differ - differ_changed)
for e in examples:
    print("      ", e)
print()
print("FALLBACK for the unmatched")
print("  their seed exists in our human set:", miss_seed_ok, "/", miss)
