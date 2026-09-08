"""One miRNA + one gene, through every tool we have. The prototype results row."""
import sqlite3, sys
sys.path.insert(0, "src")
from resolve import resolve_mirna, resolve_gene
from tools.seed import find_sites

DB = "data/processed/mirna.db"
mir_in = sys.argv[1] if len(sys.argv) > 1 else "hsa-miR-21-5p"
gene_in = sys.argv[2] if len(sys.argv) > 2 else "PDCD4"

con = sqlite3.connect(DB)
m = resolve_mirna(con, mir_in)
g = resolve_gene(con, gene_in)
if not m or "accession" not in m:
    sys.exit("miRNA not resolved: %r -> %r" % (mir_in, m))
if not g or "entrez" not in g:
    sys.exit("gene not resolved: %r -> %r" % (gene_in, g))
print("miRNA :", m["name"], m["accession"], " seed", m["seed"], "(%s)" % m["matched_by"])
print("gene  :", g["symbol"], g["entrez"], "(%s)" % g["matched_by"])

mseq = con.execute("SELECT sequence FROM mirnas WHERE accession=?",
                   (m["accession"],)).fetchone()[0]
tx = con.execute("SELECT refseq, length, sequence FROM transcripts "
                 "WHERE entrez=? AND mane_status='MANE Select'", (g["entrez"],)).fetchone()
if tx is None:
    sys.exit("no MANE Select transcript for " + g["symbol"])
refseq, length, target = tx
regions = con.execute("SELECT region, start_pos, end_pos FROM regions WHERE refseq=?",
                      (refseq,)).fetchall()
print("transcript:", refseq, length, "nt  regions", regions)

def region_of(pos):
    for name, s, e in regions:
        if s <= pos <= e:
            return name
    return "?"

sites = find_sites(mseq, target, m["name"], refseq)
print()
print("OUR SEED TOOL:", len(sites), "sites")
for s in sites:
    print("   %-9s at %5d  (%s)" % (s["site_type"], s["position"], region_of(s["position"])))

ts = con.execute("SELECT seed, family, conservation FROM targetscan_mirnas WHERE accession=?",
                 (m["accession"],)).fetchone()
print()
print("TARGETSCAN v8.0:")
if ts is None:
    print("   this miRNA is not in TargetScan")
else:
    ts_seed, family, cons = ts
    print("   family", family, " seed", ts_seed, " conservation", cons,
          " seed unchanged:", ts_seed == m["seed"])
    row = con.execute("SELECT sites_conserved, sites_nonconserved, context_score, "
                      "aggregate_pct, in_default FROM targetscan WHERE seed=? AND entrez=?",
                      (ts_seed, g["entrez"])).fetchone()
    if row is None:
        print("   no predicted site in this gene")
    else:
        pct = "n/a" if row[3] == 0 else "%.3f" % row[3]
        print("   conserved %d  nonconserved %d  context++ %.3f  PCT %s  in default set %d"
              % (row[0], row[1], row[2], pct, row[4]))

print()
print("MIRTARBASE 10.0:")
mt = con.execute("SELECT n_strong_func, n_weak_func, n_strong_nonfunc, n_weak_nonfunc, "
                 "n_sites, pmids FROM mirtarbase WHERE accession=? AND entrez=?",
                 (m["accession"], g["entrez"])).fetchone()
if mt is None:
    print("   no experimental record  ->  NOVEL")
else:
    sf, wf, sn, wn, ns, pm = mt
    status = ("VALIDATED (strong)" if sf else
              "REPORTED (high-throughput)" if wf else "EVIDENCE OF NO EFFECT")
    print("   status:", status)
    print("   functional     strong %d  weak %d" % (sf, wf))
    print("   non-functional strong %d  weak %d" % (sn, wn))
    print("   curated site sequences:", ns)
    print("   PMIDs:", (pm or "")[:70])
