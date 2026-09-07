"""Load miRBase Release 23 miRNAs, plus Release 22 names as aliases."""
import hashlib, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, ".")
from src.db import connect
from src.tools.seed import get_seed

R23 = "data/raw/mature_r23.fa"
R22 = "data/raw/mature_r22.fa"
CHANGED = "manifests/seed_changed_accessions.txt"
NAMES = {"hsa": "human", "mmu": "mouse", "rno": "rat"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def species_of(name):
    prefix = name.split("-")[0]
    return prefix


def read_fasta(path):
    """Yield (name, accession, sequence) from a miRBase mature.fa."""
    name = acc = None
    parts = []
    for line in Path(path).read_text().splitlines():
        if line.startswith(">"):
            if acc:
                yield name, acc, "".join(parts)
            f = line[1:].split()
            name = f[0]
            acc = f[1] if len(f) > 1 else None
            parts = []
        else:
            parts.append(line.strip())
    if acc:
        yield name, acc, "".join(parts)


con = connect()
cur = con.cursor()
changed = set(Path(CHANGED).read_text().split())
print("seed-changed accessions loaded:", len(changed))


m_rows, a_rows = [], []
n23 = skipped = 0
for name, acc, seq in read_fasta(R23):
    n23 += 1
    if not acc or len(seq) < 8:
        skipped += 1
        continue
    try:
        sd = get_seed(seq)
    except ValueError:
        skipped += 1
        continue
    m_rows.append((acc, name, seq, sd, species_of(name), "23",
                   1 if acc in changed else 0))
    a_rows.append((name, acc, "miRBase 23"))

cur.executemany("INSERT OR REPLACE INTO mirnas VALUES (?,?,?,?,?,?,?)", m_rows)
cur.executemany("INSERT OR IGNORE INTO mirna_aliases VALUES (?,?,?)", a_rows)
con.commit()
print("Release 23 read:", n23, " loaded:", len(m_rows), " skipped:", skipped)

a22 = []
n22 = 0
for name, acc, seq in read_fasta(R22):
    n22 += 1
    if acc:
        a22.append((name, acc, "miRBase 22"))
cur.executemany("INSERT OR IGNORE INTO mirna_aliases VALUES (?,?,?)", a22)
con.commit()
print("Release 22 read:", n22, " alias rows offered:", len(a22))


for label, path, ver in [("miRBase_mature_23", R23, "23"), ("miRBase_mature_22", R22, "22")]:
    cur.execute("INSERT OR REPLACE INTO data_sources VALUES (?,?,?,?,?,?,?)", (
        label, ver, "https://www.mirbase.org/download/",
        date.today().isoformat(), Path(path).stat().st_size, sha256(path),
        "mature.fa; 22 stands in for the 22.x series (identical entry count)"))
con.commit()

def q(sql):
    return cur.execute(sql).fetchone()[0]

print()
print("mirnas total       ", q("SELECT COUNT(*) FROM mirnas"))
print("  human            ", q("SELECT COUNT(*) FROM mirnas WHERE species='hsa'"))
print("  mouse            ", q("SELECT COUNT(*) FROM mirnas WHERE species='mmu'"))
print("  rat              ", q("SELECT COUNT(*) FROM mirnas WHERE species='rno'"))
print("  seed changed     ", q("SELECT COUNT(*) FROM mirnas WHERE seed_changed=1"))
print("aliases total      ", q("SELECT COUNT(*) FROM mirna_aliases"))
print("  pointing nowhere ", q("SELECT COUNT(*) FROM mirna_aliases a LEFT JOIN mirnas m ON a.accession=m.accession WHERE m.accession IS NULL"), "(removed in 23 - expected)")
print()
print("BRIDGE TEST - both names must give the same accession:")
for nm in ("hsa-miR-107", "hsa-miR-107-3p", "hsa-let-7a-5p"):
    r = cur.execute("SELECT a.accession, m.name, m.seed FROM mirna_aliases a LEFT JOIN mirnas m ON a.accession=m.accession WHERE a.alias=?", (nm,)).fetchone()
    print("  %-16s -> %s" % (nm, r))
con.close()
