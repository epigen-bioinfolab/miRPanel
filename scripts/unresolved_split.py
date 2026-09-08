"""Split unresolved miRTarBase names into retired vs pre-release-20."""
import sqlite3

con = sqlite3.connect("data/processed/mirna.db")
names = {nm: c for nm, c in con.execute(
    "SELECT mirna_name, COUNT(*) FROM mirtarbase_evidence "
    "WHERE accession IS NULL GROUP BY mirna_name")}

known = set()
for v in ("20", "21", "22", "23"):
    for line in open("data/raw/mature_r%s.fa" % v):
        if line.startswith(">"):
            known.add(line[1:].split()[0])

retired = {n: c for n, c in names.items() if n in known}
older = {n: c for n, c in names.items() if n not in known}
print("unresolved names", len(names), " rows", sum(names.values()))
print("  retired (in a release we have, gone from 23):", len(retired), sum(retired.values()))
print("  older than release 20                       :", len(older), sum(older.values()))
print("  top retired:", sorted(retired.items(), key=lambda x: -x[1])[:6])
print("  top older  :", sorted(older.items(), key=lambda x: -x[1])[:6])
