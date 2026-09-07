"""Resolve TargetScan genes onto MANE, and check whether the chosen transcript agrees."""
import csv, sqlite3

GI = "data/raw/Gene_info.txt"
DB = "data/processed/mirna.db"

def base(x):
    return x.split(".")[0]

rows = [r for r in csv.DictReader(open(GI), delimiter="\t")
        if r["Species ID"] == "9606"]

con = sqlite3.connect(DB)
by_ensg = {b: e for b, e in con.execute(
    "SELECT ensembl_base, entrez FROM genes WHERE ensembl_base IS NOT NULL")}
by_sym = {s: e for s, e in con.execute("SELECT symbol, entrez FROM genes")}
by_alias = {a: e for a, e in con.execute("SELECT alias, entrez FROM gene_aliases")}
mane_tx = {b: e for b, e in con.execute(
    "SELECT ensembl_base, entrez FROM transcripts WHERE ensembl_base IS NOT NULL")}

genes = {}
for r in rows:
    g = base(r["Gene ID"])
    genes.setdefault(g, {"sym": r["Gene symbol"], "rep": None})
    if r["Representative transcript?"] == "1":
        genes[g]["rep"] = base(r["Transcript ID"])

step = {"ensembl": 0, "symbol": 0, "alias": 0, "none": 0}
resolved = {}
for g, info in genes.items():
    if g in by_ensg:
        resolved[g] = by_ensg[g]; step["ensembl"] += 1
    elif info["sym"] in by_sym:
        resolved[g] = by_sym[info["sym"]]; step["symbol"] += 1
    elif info["sym"] in by_alias:
        resolved[g] = by_alias[info["sym"]]; step["alias"] += 1
    else:
        step["none"] += 1

print("TargetScan human genes :", len(genes))
print("RESOLVER CASCADE")
print("  matched on Ensembl gene:", step["ensembl"])
print("  then on gene symbol    :", step["symbol"])
print("  then on gene alias     :", step["alias"])
print("  unresolved             :", step["none"])
print("  total resolved         :", len(resolved))

same = diff = norep = 0
for g, ent in resolved.items():
    rep = genes[g]["rep"]
    if rep is None:
        norep += 1
    elif mane_tx.get(rep) == ent:
        same += 1
    else:
        diff += 1
print()
print("REPRESENTATIVE TRANSCRIPT vs MANE (resolved genes only)")
print("  TargetScan's pick IS the MANE transcript:", same)
print("  it is a different transcript            :", diff)
print("  no representative flagged               :", norep)
