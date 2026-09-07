"""How does TargetScan's Gene_info join to our MANE tables?"""
import csv, sqlite3

GI = "data/raw/Gene_info.txt"
DB = "data/processed/mirna.db"

def base(x):
    """Drop an Ensembl version suffix: ENST00000263100.3 -> ENST00000263100."""
    return x.split(".")[0]

rows = [r for r in csv.DictReader(open(GI), delimiter="\t")
        if r["Species ID"] == "9606"]
print("Gene_info human rows :", len(rows))
print("  distinct ENST      :", len({base(r["Transcript ID"]) for r in rows}))
print("  distinct ENSG      :", len({base(r["Gene ID"]) for r in rows}))
print("  representative=1   :", sum(1 for r in rows if r["Representative transcript?"] == "1"))

con = sqlite3.connect(DB)
tx = {b for (b,) in con.execute("SELECT ensembl_base FROM transcripts WHERE ensembl_base IS NOT NULL")}
gn = {b for (b,) in con.execute("SELECT ensembl_base FROM genes WHERE ensembl_base IS NOT NULL")}
sym = {s for (s,) in con.execute("SELECT symbol FROM genes")}
print()
print("our MANE side: transcripts", len(tx), " genes", len(gn), " symbols", len(sym))

t_hit = len({base(r["Transcript ID"]) for r in rows} & tx)
g_hit = len({base(r["Gene ID"]) for r in rows} & gn)
s_hit = len({r["Gene symbol"] for r in rows} & sym)
print()
print("JOIN OPTIONS (distinct TargetScan entries that find a match)")
print("  by Ensembl transcript:", t_hit)
print("  by Ensembl gene      :", g_hit)
print("  by gene symbol       :", s_hit)
