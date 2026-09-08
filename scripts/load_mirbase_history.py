"""Load historical human miRNA names from miRBaseConverter into mirna_aliases."""
import csv, sys
sys.path.insert(0, "src")
from db import connect

CSVF = "data/raw/mirbase_history_hsa.csv"

con = connect()
cur = con.cursor()
rows = [(r["alias"].strip(), r["accession"].strip(), "miRBaseConverter " + r["version"])
        for r in csv.DictReader(open(CSVF))]

before = cur.execute("SELECT COUNT(*) FROM mirna_aliases").fetchone()[0]
cur.executemany("INSERT OR IGNORE INTO mirna_aliases VALUES (?,?,?)", rows)
con.commit()
after = cur.execute("SELECT COUNT(*) FROM mirna_aliases").fetchone()[0]

print("pairs offered   :", len(rows))
print("new aliases     :", after - before)
print("aliases total   :", after)
print("human ambiguous :", cur.execute(
    "SELECT COUNT(*) FROM (SELECT alias FROM mirna_aliases WHERE alias LIKE 'hsa-%' "
    "GROUP BY alias HAVING COUNT(DISTINCT accession) > 1)").fetchone()[0])
print("pointing nowhere:", cur.execute(
    "SELECT COUNT(*) FROM mirna_aliases a LEFT JOIN mirnas m ON m.accession=a.accession "
    "WHERE m.accession IS NULL").fetchone()[0])
