"""Load miRTarBase for an organism other than human.

    python3 scripts/load_mirtarbase_species.py mouse data/raw/mmu_MTI.csv
    python3 scripts/load_mirtarbase_species.py rat   data/raw/rno_MTI.csv
    python3 scripts/load_mirtarbase_species.py fly   data/raw/dme_MTI.csv

Files come from the species list at
https://awi.cuhk.edu.cn/miRTarBase/php/download.php

GENE MATCHING
-------------
miRTarBase gives an NCBI Entrez id, which would be the obvious key, but
the entrez column holds Ensembl ids for every organism except human.
So genes are matched on symbol instead. Mouse symbols match completely;
thinner annotations do not, and the miss count is printed rather than
hidden.

The evidence rows carry one line per published experiment. The summary
table collapses them to one row per miRNA-gene pair, counting strong
and weak support separately, because a pair tested once in a screen is
not the same claim as one confirmed by a reporter assay and a western
blot.
"""
import csv
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, "src")
import species as sp                                       # noqa: E402
from db import connect                                     # noqa: E402
from resolve import resolve_mirna                          # noqa: E402

SUPPORT = {"Functional MTI": (1, 1),
           "Functional MTI (Weak)": (1, 0),
           "Non-Functional MTI": (0, 1),
           "Non-Functional MTI (Weak)": (0, 0)}


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: load_mirtarbase_species.py <species> <file.csv>")
    species, path = sys.argv[1], sys.argv[2]
    rec = sp.get(species)
    code = rec["mirbase"]
    if not os.path.exists(path):
        sys.exit("missing %s" % path)

    con = connect()
    cur = con.cursor()
    cur.execute("PRAGMA cache_size = -400000")
    t0 = time.time()

    by_sym = {}
    for s, e in cur.execute("SELECT symbol, entrez FROM genes WHERE species=?",
                            (species,)):
        by_sym.setdefault(s.upper(), e)
    print("%s genes known : %s" % (species, format(len(by_sym), ",")))

    mcache = {}

    def acc_of(name):
        if name not in mcache:
            r = resolve_mirna(con, name, species)
            mcache[name] = r.get("accession") if r else None
        return mcache[name]

    cur.execute("DELETE FROM mirtarbase_evidence WHERE species=?", (code,))
    cur.execute("DELETE FROM mirtarbase WHERE entrez IN "
                "(SELECT entrez FROM genes WHERE species=?)", (species,))

    ev, pairs = [], defaultdict(lambda: {"sf": 0, "wf": 0, "sn": 0, "wn": 0,
                                         "pmids": set()})
    seen = no_mirna = no_gene = 0

    for r in rows(path):
        seen += 1
        name = (r.get("miRNA") or "").strip()
        sym = (r.get("Target Gene") or "").strip()
        acc = acc_of(name)
        e = by_sym.get(sym.upper())
        if acc is None:
            no_mirna += 1
        if e is None:
            no_gene += 1

        func, strong = SUPPORT.get((r.get("Support Type") or "").strip(),
                                   (0, 0))
        pmid = (r.get("References (PMID)") or "").strip().split(".")[0] or None
        ev.append((r.get("miRTarBase ID"), name, acc, e, sym, func, strong,
                   (r.get("Experiments") or "").strip(), pmid, code))

        if acc and e:
            p = pairs[(acc, e)]
            key = ("s" if strong else "w") + ("f" if func else "n")
            p[key] += 1
            if pmid:
                p["pmids"].add(pmid)

    cur.executemany(
        "INSERT INTO mirtarbase_evidence (mtb_id, mirna_name, accession, "
        "entrez, symbol, functional, strong, experiments, pmid, species) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", ev)

    cur.executemany(
        "INSERT OR REPLACE INTO mirtarbase VALUES (?,?,?,?,?,?,?,?)",
        [(a, e, p["sf"], p["wf"], p["sn"], p["wn"],
          p["sf"] + p["wf"] + p["sn"] + p["wn"],
          ",".join(sorted(p["pmids"])) or None)
         for (a, e), p in pairs.items()])

    cur.execute(
        "INSERT OR REPLACE INTO data_sources (name, version, url, "
        "downloaded_on, bytes, sha256, notes) VALUES (?,?,?,?,?,NULL,?)",
        ("miRTarBase-" + species, "10.0",
         "https://awi.cuhk.edu.cn/miRTarBase/php/download.php",
         time.strftime("%Y-%m-%d"), os.path.getsize(path),
         "genes matched on symbol; %d of %d rows had no gene match"
         % (no_gene, seen)))
    con.commit()

    print("rows read        : %s" % format(seen, ","))
    print("  no miRNA match : %s" % format(no_mirna, ","))
    print("  no gene match  : %s" % format(no_gene, ","))
    print("pairs stored     : %s in %.1fs"
          % (format(len(pairs), ","), time.time() - t0))


if __name__ == "__main__":
    main()
