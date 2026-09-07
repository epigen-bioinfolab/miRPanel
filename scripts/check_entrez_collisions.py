"""Do two TargetScan genes resolve to the same Entrez id?"""
import csv, sqlite3

DB = "data/processed/mirna.db"
GI = "data/raw/Gene_info.txt"

def base(x):
    return x.split(".")[0]

con = sqlite3.connect(DB)
by_ensg = {b: e for b, e in con.execute(
    "SELECT ensembl_base, entrez FROM genes WHERE ensembl_base IS NOT NULL")}
by_sym = {s: e for s, e in con.execute("SELECT symbol, entrez FROM genes")}
by_alias = {a: e for a, e in con.execute("SELECT alias, entrez FROM gene_aliases")}

ensg2e = {}
for r in csv.DictReader(open(GI), delimiter="\t"):
    if r["Species ID"] != "9606":
        continue
    g, s = base(r["Gene ID"]), r["Gene symbol"].strip()
    e = by_ensg.get(g) or by_sym.get(s) or by_alias.get(s)
    if e:
        ensg2e[g] = e

rev = {}
for g, e in ensg2e.items():
    rev.setdefault(e, []).append(g)
multi = {e: gs for e, gs in rev.items() if len(gs) > 1}
print("resolved ENSGs      :", len(ensg2e))
print("distinct entrez     :", len(rev))
print("entrez with >1 ENSG :", len(multi))
for e, gs in list(multi.items())[:5]:
    print("   ", e, gs)
