"""Check the resolver against tricky real inputs."""
import sqlite3, sys
sys.path.insert(0, "src")
from resolve import resolve_mirna, resolve_gene

con = sqlite3.connect("data/processed/mirna.db")

MIRNAS = ["hsa-miR-21-5p", "hsa-miR-107", "hsa-miR-137", "hsa-mir-506-3p",
          "miR-183-5p", "MIMAT0000076", "  hsa-let-7a-5p  ", "not-a-mirna"]
GENES = ["PDCD4", "6541", "ENSG00000121410", "NM_014456.5", "H731", "nosuchgene"]

for t in MIRNAS:
    r = resolve_mirna(con, t)
    print("%-22r -> %s" % (t, None if r is None else
          (r.get("accession"), r.get("name"), r["matched_by"])))
print()
for t in GENES:
    r = resolve_gene(con, t)
    print("%-22r -> %s" % (t, None if r is None else
          (r.get("entrez"), r.get("symbol"), r["matched_by"])))
