"""Load miRTarBase 10.0 (human) into evidence, sites and summary tables."""
import collections, csv, datetime, hashlib, os, sys, time
sys.path.insert(0, "src")
from db import connect
from resolve import resolve_mirna, resolve_gene

RAW = "data/raw"
MTI = RAW + "/mirtarbase_hsa_MTI.csv"
SITES = RAW + "/mirtarbase_target_sites.csv"
HUMAN = "hsa"

SUPPORT = {"Functional MTI": (1, 1),
           "Functional MTI (Weak)": (1, 0),
           "Non-Functional MTI": (0, 1),
           "Non-Functional MTI (Weak)": (0, 0)}

def rows(path):
    """Yield dict rows; utf-8-sig strips the byte-order mark."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)

def ent(x):
    """'6541.0' -> '6541'; blank -> None."""
    x = (x or "").strip()
    return x.split(".")[0] if x else None

con = connect()
cur = con.cursor()
cur.execute("PRAGMA cache_size = -400000")
t0 = time.time()

known_genes = {e for (e,) in cur.execute("SELECT entrez FROM genes")}
mcache, gcache = {}, {}

def acc_of(name):
    """Resolve a miRNA name to an accession, cached."""
    if name not in mcache:
        r = resolve_mirna(con, name)
        mcache[name] = r.get("accession") if r else None
    return mcache[name]

def gene_of(raw_entrez, symbol):
    """Prefer the given Entrez id; fall back to the symbol through the resolver."""
    e = ent(raw_entrez)
    if e and e in known_genes:
        return e
    if symbol not in gcache:
        r = resolve_gene(con, symbol)
        gcache[symbol] = r.get("entrez") if r else None
    return gcache[symbol]

seen = collections.Counter()
for r in rows(MTI):
    if r["Species (miRNA)"] == HUMAN:
        seen[r["Support Type"].strip()] += 1
unknown = {k: v for k, v in seen.items() if k not in SUPPORT}
print("support types in file:")
for k, v in seen.most_common():
    print("   ", k, v)
if unknown:
    raise SystemExit("UNKNOWN support types, stopping: %r" % unknown)
print("pre-scan ok  %.0fs" % (time.time() - t0))

cur.execute("DELETE FROM mirtarbase_evidence")
INS = "INSERT INTO mirtarbase_evidence VALUES (" + ",".join("?" * 11) + ")"
batch, n, no_acc, no_gene = [], 0, 0, 0
for r in rows(MTI):
    if r["Species (miRNA)"] != HUMAN:
        continue
    func, strong = SUPPORT[r["Support Type"].strip()]
    nm, sym = r["miRNA"].strip(), r["Target Gene"].strip()
    acc = acc_of(nm)
    e = gene_of(r["Target Gene (Entrez ID)"], sym)
    no_acc += acc is None
    no_gene += e is None
    batch.append((None, r["miRTarBase ID"].strip(), nm, acc, e, sym,
                  func, strong, r["Experiments"].strip(),
                  ent(r["References (PMID)"]), HUMAN))
    n += 1
    if len(batch) >= 200000:
        cur.executemany(INS, batch)
        batch = []
        print("  evidence %d  %.0fs" % (n, time.time() - t0))
if batch:
    cur.executemany(INS, batch)
con.commit()
print("evidence rows:", n, " no accession:", no_acc, " no gene:", no_gene)

cur.execute("DELETE FROM mirtarbase_sites")
sbatch, sn = [], 0
for r in rows(SITES):
    if r["Species (miRNA)"] != HUMAN:
        continue
    st = r["Support Type"].strip()
    site = r["Target Site"].strip().upper().replace("U", "T")
    if st not in SUPPORT or not site:
        continue
    func, strong = SUPPORT[st]
    sbatch.append((r["miRTarBase ID"].strip(), acc_of(r["miRNA"].strip()),
                   gene_of(r["Target Gene (Entrez ID)"], r["Target Gene"].strip()),
                   site, func, strong, ent(r["References (PMID)"])))
    sn += 1
    if len(sbatch) >= 200000:
        cur.executemany("INSERT INTO mirtarbase_sites VALUES (?,?,?,?,?,?,?)", sbatch)
        sbatch = []
if sbatch:
    cur.executemany("INSERT INTO mirtarbase_sites VALUES (?,?,?,?,?,?,?)", sbatch)
con.commit()
print("site rows    :", sn, " %.0fs" % (time.time() - t0))

cur.execute("DELETE FROM mirtarbase")
cur.execute("""INSERT INTO mirtarbase
    SELECT accession, entrez,
           SUM(functional=1 AND strong=1), SUM(functional=1 AND strong=0),
           SUM(functional=0 AND strong=1), SUM(functional=0 AND strong=0),
           0, GROUP_CONCAT(DISTINCT pmid)
    FROM mirtarbase_evidence
    WHERE accession IS NOT NULL AND entrez IS NOT NULL
    GROUP BY accession, entrez""")
cur.execute("""UPDATE mirtarbase SET n_sites =
    (SELECT COUNT(*) FROM mirtarbase_sites s
     WHERE s.accession = mirtarbase.accession AND s.entrez = mirtarbase.entrez)""")
con.commit()

def q(sql):
    return cur.execute(sql).fetchone()[0]

print("VERIFY")
print("  summary pairs      ", q("SELECT COUNT(*) FROM mirtarbase"))
print("  strong functional  ", q("SELECT COUNT(*) FROM mirtarbase WHERE n_strong_func>0"))
print("  weak only          ", q("SELECT COUNT(*) FROM mirtarbase WHERE n_strong_func=0 AND n_weak_func>0"))
print("  contradicted       ", q("SELECT COUNT(*) FROM mirtarbase WHERE n_strong_func>0 AND n_strong_nonfunc>0"))
print("  non-functional only", q("SELECT COUNT(*) FROM mirtarbase WHERE n_strong_func=0 AND n_weak_func=0"))
print("  pairs with sites   ", q("SELECT COUNT(*) FROM mirtarbase WHERE n_sites>0"))

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()

today = datetime.date.today().isoformat()
for nm, p in (("mirtarbase_mti", MTI), ("mirtarbase_sites", SITES)):
    cur.execute("INSERT OR REPLACE INTO data_sources VALUES (?,?,?,?,?,?,?)",
                (nm, "10.0", "awi.cuhk.edu.cn/miRTarBase", today,
                 os.path.getsize(p), sha256(p),
                 "human only; site says release 11.0 but files served are 10.0"))
con.commit()
print("done %.0fs" % (time.time() - t0))
