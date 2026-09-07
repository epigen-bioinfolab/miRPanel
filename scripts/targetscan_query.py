"""Look up TargetScan predictions for one miRNA, end to end."""
import sqlite3, sys

DB = "data/processed/mirna.db"
name = sys.argv[1] if len(sys.argv) > 1 else "hsa-miR-21-5p"

con = sqlite3.connect(DB)
row = con.execute("SELECT accession, name, seed FROM mirnas WHERE name=?", (name,)).fetchone()
if row is None:
    row = con.execute("SELECT m.accession, m.name, m.seed FROM mirna_aliases a "
                      "JOIN mirnas m ON m.accession=a.accession WHERE a.alias=?",
                      (name,)).fetchone()
if row is None:
    sys.exit("not found: " + name)
acc, canon, our_seed = row
print("input          :", name)
print("resolved to    :", canon, acc)
print("our seed (R23) :", our_seed)

ts = con.execute("SELECT ts_name, family, seed, conservation "
                 "FROM targetscan_mirnas WHERE accession=?", (acc,)).fetchone()
if ts is None:
    sys.exit("no TargetScan entry for " + acc)
ts_name, family, ts_seed, cons = ts
print("TargetScan name:", ts_name)
print("family         :", family)
print("TargetScan seed:", ts_seed, " conservation:", cons)
print("seed unchanged :", ts_seed == our_seed)

n = con.execute("SELECT COUNT(*) FROM targetscan WHERE seed=?", (ts_seed,)).fetchone()[0]
print()
print("target genes   :", n)
sql = ("SELECT g.ts_symbol, t.sites_conserved, t.sites_nonconserved, "
       "IFNULL(t.context_score,0), IFNULL(t.aggregate_pct,0), t.in_default, g.is_mane "
       "FROM targetscan t JOIN targetscan_genes g ON g.entrez=t.entrez "
       "WHERE t.seed=? ORDER BY t.context_score LIMIT 10")
print("%-12s %4s %4s %9s %6s %5s %5s" % ("gene", "cons", "non", "ctx++", "PCT", "dflt", "mane"))
for r in con.execute(sql, (ts_seed,)):
    print("%-12s %4d %4d %9.3f %6.3f %5d %5d" % r)

q = ("SELECT g.ts_symbol, t.sites_conserved, t.sites_nonconserved, t.context_score, "
     "t.aggregate_pct, t.in_default FROM targetscan t "
     "JOIN targetscan_genes g ON g.entrez=t.entrez WHERE t.seed=? AND g.ts_symbol=?")
print()
print("PDCD4:", con.execute(q, (ts_seed, "PDCD4")).fetchone())
