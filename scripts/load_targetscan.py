"""Load TargetScan v8.0 (human) into targetscan_mirnas, targetscan_genes, targetscan."""
import csv, datetime, hashlib, os, sys, time
sys.path.insert(0, "src")
from db import connect

RAW = "data/raw"
FI = RAW + "/miR_Family_Info.txt"
GI = RAW + "/Gene_info.txt"
ALLP = RAW + "/Summary_Counts.all_predictions.txt"
DEFP = RAW + "/Summary_Counts.default_predictions.txt"
HUMAN = "9606"

def base(x):
    """Drop an Ensembl version suffix."""
    return x.split(".")[0]

def dna(s):
    """RNA -> DNA, uppercase, trimmed."""
    return s.strip().upper().replace("U", "T")

def num(s):
    """Text field -> float, or None where TargetScan wrote NULL."""
    s = s.strip()
    return None if s in ("", "NULL", "NA") else float(s)

con = connect()
cur = con.cursor()
cur.execute("PRAGMA cache_size = -400000")
cur.execute("PRAGMA temp_store = MEMORY")
t0 = time.time()

mrows = []
for r in csv.DictReader(open(FI), delimiter="\t"):
    if r["Species ID"] != HUMAN:
        continue
    mrows.append((r["MiRBase Accession"].strip(), r["MiRBase ID"].strip(),
                  r["miR family"].strip(), dna(r["Seed+m8"]),
                  int(r["Family Conservation?"]), "hsa"))
cur.execute("DELETE FROM targetscan_mirnas")
skipped = len(mrows)
mrows = [m for m in mrows if m[0]]
skipped -= len(mrows)
cur.executemany("INSERT INTO targetscan_mirnas VALUES (?,?,?,?,?,?)", mrows)
con.commit()
print("targetscan_mirnas :", len(mrows), " skipped, no accession:", skipped)

by_ensg = {b: e for b, e in cur.execute(
    "SELECT ensembl_base, entrez FROM genes WHERE ensembl_base IS NOT NULL")}
by_sym = {s: e for s, e in cur.execute("SELECT symbol, entrez FROM genes")}
by_alias = {a: e for a, e in cur.execute("SELECT alias, entrez FROM gene_aliases")}
mane_tx = {b for (b,) in cur.execute(
    "SELECT ensembl_base FROM transcripts WHERE ensembl_base IS NOT NULL")}

tx2gene = {}
for r in csv.DictReader(open(GI), delimiter="\t"):
    if r["Species ID"] != HUMAN:
        continue
    tx2gene[base(r["Transcript ID"])] = (base(r["Gene ID"]), r["Gene symbol"].strip())

def entrez_of(ensg, symbol):
    """Resolve a TargetScan gene to our Entrez id, or None."""
    return by_ensg.get(ensg) or by_sym.get(symbol) or by_alias.get(symbol)

ensg2sym, rep_tx = {}, {}
for r in csv.DictReader(open(GI), delimiter="\t"):
    if r["Species ID"] != HUMAN:
        continue
    g = base(r["Gene ID"])
    ensg2sym[g] = r["Gene symbol"].strip()
    if r["Representative transcript?"] == "1":
        rep_tx[g] = base(r["Transcript ID"])

chosen = {}
for g in sorted(ensg2sym):
    e = entrez_of(g, ensg2sym[g])
    if e is None:
        continue
    prev = chosen.get(e)
    if prev is None or (rep_tx.get(g) in mane_tx and rep_tx.get(prev) not in mane_tx):
        chosen[e] = g

print("Gene_info transcripts:", len(tx2gene), " genes chosen:", len(chosen))

in_default = set()
with open(DEFP) as fh:
    next(fh)
    for line in fh:
        f = line.split("\t")
        if f[3] == HUMAN:
            in_default.add((base(f[0]), dna(f[2])))
print("default keys      :", len(in_default))

INS = "INSERT INTO targetscan VALUES (" + ",".join("?" * 18) + ")"
genes, batch, n, dropped, missing, collided = {}, [], 0, 0, 0, 0
cur.execute("DELETE FROM targetscan")
cur.execute("DELETE FROM targetscan_genes")

with open(ALLP) as fh:
    next(fh)
    for line in fh:
        f = line.rstrip("\n").split("\t")
        if f[3] != HUMAN:
            continue
        tx = base(f[0])
        meta = tx2gene.get(tx)
        if meta is None:
            missing += 1
            continue
        e = entrez_of(meta[0], meta[1])
        if e is None:
            dropped += 1
            continue
        if chosen.get(e) != meta[0]:
            collided += 1
            continue
        genes.setdefault(e, (e, tx, meta[0], meta[1], 1 if tx in mane_tx else 0))
        sd = dna(f[2])
        batch.append((sd, e, int(f[4]), int(f[5]), int(f[6]), int(f[7]),
                      int(f[8]), int(f[9]), int(f[10]), int(f[11]), int(f[12]),
                      num(f[14]), num(f[15]), num(f[16]),
                      num(f[17]), num(f[18]), num(f[19]),
                      1 if (tx, sd) in in_default else 0))
        n += 1
        if len(batch) >= 200000:
            cur.executemany(INS, batch)
            batch = []
            print("  rows %d  %.0fs" % (n, time.time() - t0))
if batch:
    cur.executemany(INS, batch)
cur.executemany("INSERT INTO targetscan_genes VALUES (?,?,?,?,?)", list(genes.values()))
con.commit()
print("targetscan rows   :", n, " dropped:", dropped, " missing tx:", missing, " collided:", collided)

def q(sql):
    return cur.execute(sql).fetchone()[0]

print("VERIFY")
print("  rows in table       ", q("SELECT COUNT(*) FROM targetscan"))
print("  distinct seeds      ", q("SELECT COUNT(DISTINCT seed) FROM targetscan"))
print("  distinct genes      ", q("SELECT COUNT(DISTINCT entrez) FROM targetscan"))
print("  in_default rows     ", q("SELECT COUNT(*) FROM targetscan WHERE in_default=1"))
print("  orphan genes (0 ok) ", q("SELECT COUNT(*) FROM targetscan t LEFT JOIN genes g ON g.entrez=t.entrez WHERE g.entrez IS NULL"))
print("  is_mane genes       ", q("SELECT COUNT(*) FROM targetscan_genes WHERE is_mane=1"))

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()

today = datetime.date.today().isoformat()
for nm, p in (("targetscan_families", RAW + "/ts_miR_Family_Info.txt.zip"),
              ("targetscan_geneinfo", RAW + "/ts_Gene_info.txt.zip"),
              ("targetscan_predictions", RAW + "/ts_Summary_Counts.all_predictions.txt.zip")):
    cur.execute("INSERT OR REPLACE INTO data_sources VALUES (?,?,?,?,?,?,?)",
                (nm, "vert_80", "targetscan.org/vert_80", today,
                 os.path.getsize(p), sha256(p), "human only"))
con.commit()
print("done  %.0fs" % (time.time() - t0))
