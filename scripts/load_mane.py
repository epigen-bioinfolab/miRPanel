"""Load MANE genes, transcripts, regions and aliases into the database."""
import csv, gzip, hashlib, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, ".")
from src.db import connect
from src.mane import transcripts, regions, GBFF

SUMMARY = "data/raw/MANE.v1.5.summary.txt.gz"
SPECIES = "human"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def base(x):
    return x.split(".")[0] if x else None


def load_summary(path=SUMMARY):
    out = {}
    with gzip.open(path, "rt") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        reader.fieldnames = [f.lstrip("#") for f in reader.fieldnames]
        for row in reader:
            out[base(row["RefSeq_nuc"])] = row
    return out


summary = load_summary()
print("summary rows loaded:", len(summary))

con = connect()
cur = con.cursor()
g_rows, t_rows, r_rows, a_rows = [], [], [], []
seen = set()


def flush():
    cur.executemany("INSERT OR IGNORE INTO genes VALUES (?,?,?,?,?,?,?)", g_rows)
    cur.executemany("INSERT OR REPLACE INTO transcripts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", t_rows)
    cur.executemany("INSERT OR REPLACE INTO regions VALUES (?,?,?,?,?)", r_rows)
    cur.executemany("INSERT OR IGNORE INTO gene_aliases VALUES (?,?,?)", a_rows)
    con.commit()
    g_rows.clear(); t_rows.clear(); r_rows.clear(); a_rows.clear()


n = matched = skipped = 0
for rec in transcripts():
    n += 1
    b = rec["refseq_base"]
    s = summary.get(b)
    if s:
        matched += 1
    entrez = rec["entrez"] or (s["NCBI_GeneID"].replace("GeneID:", "") if s else None)
    if not entrez:
        skipped += 1
        continue
    symbol = rec["symbol"] or (s["symbol"] if s else "")
    ens_gene = s["Ensembl_Gene"] if s else None
    ens_nuc = s["Ensembl_nuc"] if s else None
    if entrez not in seen:
        seen.add(entrez)
        g_rows.append((entrez, symbol, ens_gene, base(ens_gene),
                       s["HGNC_ID"] if s else None, s["name"] if s else None, SPECIES))
    t_rows.append((rec["refseq"], b, ens_nuc, base(ens_nuc), entrez, symbol,
                   s["MANE_status"] if s else None,
                   rec["length"], rec["cds_start"], rec["cds_end"],
                   "coding" if rec["cds_start"] else "noncoding",
                   SPECIES, rec["sequence"]))
    for name, st, en in regions(rec):
        r_rows.append((rec["refseq"], name, st, en, en - st + 1))
    for a in [symbol] + [x.strip() for x in (rec["synonyms"] or "").split(";")]:
        if a:
            a_rows.append((a, entrez, "MANE"))
    if len(t_rows) >= 500:
        flush()
        print("  loaded", n, end="\r")
flush()


cur.execute("INSERT OR REPLACE INTO data_sources VALUES (?,?,?,?,?,?,?)", (
    "MANE", "v1.5",
    "https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human/current/",
    date.today().isoformat(), Path(GBFF).stat().st_size, sha256(GBFF),
    "GRCh38.p14; RefSeq annotation GCF_000001405.40-RS_2025_08; Ensembl 116"))
con.commit()

def q(sql):
    return cur.execute(sql).fetchone()[0]

print()
print("matched in summary ", matched, "of", n)
print("skipped (no gene)  ", skipped)
print("genes              ", q("SELECT COUNT(*) FROM genes"))
print("transcripts        ", q("SELECT COUNT(*) FROM transcripts"))
print("  coding           ", q("SELECT COUNT(*) FROM transcripts WHERE biotype='coding'"))
print("  noncoding        ", q("SELECT COUNT(*) FROM transcripts WHERE biotype='noncoding'"))
print("regions            ", q("SELECT COUNT(*) FROM regions"))
print("gene aliases       ", q("SELECT COUNT(*) FROM gene_aliases"))
print("orphan transcripts ", q("SELECT COUNT(*) FROM transcripts t LEFT JOIN genes g ON t.entrez=g.entrez WHERE g.entrez IS NULL"), " <- must be 0")
print("malformed regions  ", q("SELECT COUNT(*) FROM regions WHERE end_pos<start_pos OR length<>end_pos-start_pos+1"), " <- must be 0")
print("regions not summing", q("SELECT COUNT(*) FROM (SELECT r.refseq FROM regions r JOIN transcripts t ON r.refseq=t.refseq GROUP BY r.refseq, t.length HAVING SUM(r.length)<>t.length)"), " <- must be 0")
print()
for row in cur.execute("SELECT region, start_pos, end_pos, length FROM regions WHERE refseq LIKE 'NM_014456%' ORDER BY start_pos"):
    print("  PDCD4", row)
print("  alias check:", cur.execute("SELECT symbol FROM genes WHERE entrez=(SELECT entrez FROM gene_aliases WHERE alias='H731')").fetchone())
con.close()
