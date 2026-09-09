"""Prove the parallel RNAhybrid produced exactly what the serial one did.

    python scripts/check_rnahybrid_parity.py <baseline_job> <new_job>
"""
import hashlib, sys
sys.path.insert(0, "src")
import db

con = db.connect()

def signature(job):
    rows = con.execute(
        "SELECT refseq, pos_start, pos_end, score, region FROM results "
        "WHERE job_id=? AND tool='rnahybrid' ORDER BY refseq, pos_start, score",
        (job,)).fetchall()
    genes = con.execute(
        "SELECT COUNT(DISTINCT entrez) FROM results WHERE job_id=? AND "
        "tool='rnahybrid'", (job,)).fetchone()[0]
    digest = hashlib.sha256(repr(rows).encode()).hexdigest()[:16]
    return len(rows), genes, digest

a, b = sys.argv[1], sys.argv[2]
ra, rb = signature(a), signature(b)
print("baseline %s : %d records, %d genes, sha %s" % ((a,) + ra))
print("parallel %s : %d records, %d genes, sha %s" % ((b,) + rb))
print()
if ra == rb:
    print("IDENTICAL - every record matches, position for position")
else:
    print("DIFFERENT - do not keep the parallel version")
    if ra[0] != rb[0]:
        print("  record count differs by", rb[0] - ra[0])
