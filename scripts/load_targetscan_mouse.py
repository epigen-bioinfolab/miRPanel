"""Load TargetScan mouse predictions.

    python3 scripts/load_targetscan_mouse.py

Needs two files in data/raw:
    mmu_ts_context.txt   Predicted Targets context++ scores (default)
    mmu_ts_family.txt    miR Family Info

Both come from the vertebrate release and cover many species, so rows
are filtered to tax id 10090.

HOW THIS DIFFERS FROM THE HUMAN LOADER
--------------------------------------
The human load reads Summary_Counts, which is already one row per
gene with site-type counts. This file is one row per SITE, so the
counts are built here by grouping on seed and gene.

It also needs no Gene_info lookup: the Ensembl gene id is in the first
column, and the mouse genes table is keyed on Ensembl ids anyway.

Every row in the default-predictions file is a conserved site, so the
non-conserved counts are zero rather than unknown. Aggregate P_CT is
not in this file and is left null rather than guessed.
"""
import csv
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, "src")
from db import connect                                     # noqa: E402

RAW = "data/raw"
CTX = os.path.join(RAW, "mmu_ts_context.txt")
FAM = os.path.join(RAW, "mmu_ts_family.txt")
TAXID = "10090"
SPECIES = "mouse"
MIRBASE = "mmu"

#: TargetScan's numeric site types.
SITE = {"1": "7mer-A1", "2": "7mer-m8", "3": "8mer"}


def base(x):
    return x.split(".")[0]


def dna(s):
    return s.strip().upper().replace("U", "T")


def num(s):
    s = (s or "").strip()
    return None if s in ("", "NULL", "NA") else float(s)


con = connect()
cur = con.cursor()
cur.execute("PRAGMA cache_size = -400000")
cur.execute("PRAGMA temp_store = MEMORY")
t0 = time.time()

for path in (CTX, FAM):
    if not os.path.exists(path):
        sys.exit("missing %s" % path)

# ── miRNAs ──────────────────────────────────────────────────────────
seed_of = {}
mrows = []
for r in csv.DictReader(open(FAM), delimiter="\t"):
    if r["Species ID"].strip() != TAXID:
        continue
    acc = r["MiRBase Accession"].strip()
    name = r["MiRBase ID"].strip()
    seed = dna(r["Seed+m8"])
    seed_of[name] = seed
    if acc:
        mrows.append((acc, name, r["miR family"].strip(), seed,
                      int(r["Family Conservation?"]), MIRBASE))

cur.execute("DELETE FROM targetscan_mirnas WHERE species=?", (MIRBASE,))
cur.executemany("INSERT OR REPLACE INTO targetscan_mirnas "
                "VALUES (?,?,?,?,?,?)", mrows)
con.commit()
print("miRNAs           : %s  (%s with a seed)" % (len(mrows), len(seed_of)))

# ── genes ───────────────────────────────────────────────────────────
by_ensg = {b: e for b, e in cur.execute(
    "SELECT ensembl_base, entrez FROM genes WHERE species=? "
    "AND ensembl_base IS NOT NULL", (SPECIES,))}
canonical_tx = {b for (b,) in cur.execute(
    "SELECT ensembl_base FROM transcripts WHERE species=? AND canonical=1",
    (SPECIES,))}
print("mouse genes known: %s" % len(by_ensg))

# ── sites ───────────────────────────────────────────────────────────
# Grouped on (seed, gene): the stored row is one prediction per miRNA
# family per gene, matching how the human table is keyed.
agg = defaultdict(lambda: {"n": 0, "8mer": 0, "7mer-m8": 0, "7mer-A1": 0,
                           "best": None, "sum": 0.0})
genes = {}
seen, skipped_gene, skipped_seed = 0, 0, 0

with open(CTX) as fh:
    next(fh)
    for line in fh:
        f = line.rstrip("\n").split("\t")
        if len(f) < 12 or f[3].strip() != TAXID:
            continue
        seen += 1
        ensg = base(f[0])
        e = by_ensg.get(ensg)
        if e is None:
            skipped_gene += 1
            continue
        seed = seed_of.get(f[4].strip())
        if not seed:
            skipped_seed += 1
            continue

        a = agg[(seed, e)]
        a["n"] += 1
        st = SITE.get(f[5].strip())
        if st:
            a[st] += 1
        ctx = num(f[8])
        wctx = num(f[11])
        if ctx is not None and (a["best"] is None or ctx < a["best"]):
            a["best"] = ctx
        if wctx is not None:
            a["sum"] += wctx

        tx = base(f[2])
        genes.setdefault(e, (e, tx, ensg, f[1].strip(),
                             1 if tx in canonical_tx else 0))

print("site rows read   : %s" % format(seen, ","))
print("  no gene match  : %s" % format(skipped_gene, ","))
print("  no seed match  : %s" % format(skipped_seed, ","))
print("predictions      : %s  over %s genes"
      % (format(len(agg), ","), format(len(genes), ",")))

if not agg:
    sys.exit("nothing to load - check the files are the right release")

# ── store ───────────────────────────────────────────────────────────
# Only mouse rows are removed. Human entrez ids are numbers and mouse
# ones are Ensembl ids, so the two never collide, but deleting by the
# gene set keeps a re-run clean.
mouse_genes = set(by_ensg.values())
cur.execute("DELETE FROM targetscan WHERE entrez IN "
            "(SELECT entrez FROM genes WHERE species=?)", (SPECIES,))
cur.execute("DELETE FROM targetscan_genes WHERE entrez IN "
            "(SELECT entrez FROM genes WHERE species=?)", (SPECIES,))

cur.executemany("INSERT OR REPLACE INTO targetscan_genes VALUES (?,?,?,?,?)",
                list(genes.values()))

rows = []
for (seed, e), a in agg.items():
    rows.append((seed, e,
                 a["n"], a["8mer"], a["7mer-m8"], a["7mer-A1"],
                 0, 0, 0, 0, 0,
                 a["best"], a["sum"] or None, None,
                 None, None, None, 1))
cur.executemany("INSERT OR REPLACE INTO targetscan VALUES ("
                + ",".join("?" * 18) + ")", rows)

cur.execute(
    "INSERT OR REPLACE INTO data_sources (name, version, url, downloaded_on, "
    "bytes, sha256, notes) VALUES (?,?,?,?,?,NULL,?)",
    ("TargetScan-mouse", "v8.0 (default predictions)",
     "https://www.targetscan.org/cgi-bin/targetscan/data_download.cgi?db=mmu_80",
     time.strftime("%Y-%m-%d"),
     os.path.getsize(CTX) + os.path.getsize(FAM),
     "conserved sites only; counts built per site; aggregate P_CT not "
     "published in this file"))
con.commit()
print("stored           : %s rows in %.1fs" % (format(len(rows), ","),
                                               time.time() - t0))
