"""How big is the gene list under each candidate rule?

    python scripts/enrichment_sets.py <job_id>

Enrichment needs a list of roughly 200-1500 genes. Below that there is no
power; above it, everything looks enriched. This prints the size of every
rule we might use as the default, and both candidate backgrounds, so the
choice is made from numbers rather than taste.
"""
import sys
sys.path.insert(0, "src")
import db

JOB = sys.argv[1] if len(sys.argv) > 1 else None
if not JOB:
    sys.exit("usage: python scripts/enrichment_sets.py <job_id>")

con = db.connect()

if con.execute("SELECT COUNT(*) FROM results WHERE job_id=?", (JOB,)).fetchone()[0] == 0:
    sys.exit("no results for job %s" % JOB)

RULES = [
    ("seed: 8mer only",
     "tool='seed' AND site_type='8mer'"),
    ("seed: 8mer or 7mer-m8",
     "tool='seed' AND site_type IN ('8mer','7mer-m8')"),
    ("seed: any 7mer or better",
     "tool='seed' AND site_type IN ('8mer','7mer-m8','7mer-A1')"),
    ("seed: any site incl. 6mer",
     "tool='seed'"),
    ("seed 7mer+ in the 3'UTR only",
     "tool='seed' AND region='3UTR' AND site_type IN ('8mer','7mer-m8','7mer-A1')"),
    ("seed 7mer+ outside the 3'UTR",
     "tool='seed' AND region!='3UTR' AND site_type IN ('8mer','7mer-m8','7mer-A1')"),
    ("TargetScan: any score",
     "tool='targetscan'"),
    ("TargetScan: conserved site",
     "tool='targetscan' AND low_confidence=0"),
    ("TargetScan: context++ <= -0.30",
     "tool='targetscan' AND score <= -0.30"),
    ("RNAhybrid: dG <= -25",
     "tool='rnahybrid' AND score <= -25.0"),
    ("miRTarBase: strong evidence",
     "tool='mirtarbase' AND score > 0"),
]

print("job %s\n" % JOB)
print("%-38s %8s" % ("rule", "genes"))
print("-" * 48)
counts = {}
for label, where in RULES:
    n = con.execute("SELECT COUNT(DISTINCT entrez) FROM results WHERE job_id=? AND "
                    + where, (JOB,)).fetchone()[0]
    counts[label] = n
    flag = "  <- usable size" if 200 <= n <= 1500 else ""
    print("%-38s %8s%s" % (label, format(n, ","), flag))

# combinations worth knowing
def genes(where):
    return {r[0] for r in con.execute(
        "SELECT DISTINCT entrez FROM results WHERE job_id=? AND " + where, (JOB,))}

seed_strong = genes("tool='seed' AND site_type IN ('8mer','7mer-m8')")
ts_any = genes("tool='targetscan'")
ts_cons = genes("tool='targetscan' AND low_confidence=0")
print("-" * 48)
print("%-38s %8s" % ("8mer/7mer-m8 AND TargetScan scored",
                     format(len(seed_strong & ts_any), ",")))
print("%-38s %8s" % ("8mer/7mer-m8 AND TargetScan conserved",
                     format(len(seed_strong & ts_cons), ",")))

# backgrounds
print("\nbackgrounds")
print("-" * 48)
all_genes = con.execute(
    "SELECT COUNT(DISTINCT entrez) FROM transcripts "
    "WHERE mane_status='MANE Select'").fetchone()[0]
print("%-38s %8s" % ("A: every MANE Select gene", format(all_genes, ",")))
for minlen in (50, 100, 200):
    n = con.execute(
        "SELECT COUNT(DISTINCT t.entrez) FROM transcripts t JOIN regions r "
        "ON r.refseq=t.refseq WHERE t.mane_status='MANE Select' AND "
        "r.region='3UTR' AND (r.end_pos - r.start_pos + 1) >= ?",
        (minlen,)).fetchone()[0]
    print("%-38s %8s" % ("B: 3'UTR at least %d nt" % minlen, format(n, ",")))
