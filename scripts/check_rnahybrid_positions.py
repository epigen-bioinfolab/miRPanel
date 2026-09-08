"""Does pos_start..pos_end really delimit the RNAhybrid duplex on our transcript?

RNAhybrid prints N for the occasional flanking base, so N matches anything.
"""
import json, sqlite3

con = sqlite3.connect("data/processed/mirna.db")
job = con.execute("SELECT job_id FROM tool_runs WHERE tool=? ORDER BY rowid DESC LIMIT 1",
                  ("rnahybrid",)).fetchone()[0]
seqs = {r: s.replace("T", "U")
        for r, s in con.execute("SELECT refseq, sequence FROM transcripts")}
rows = con.execute("SELECT refseq, symbol, pos_start, pos_end, extra FROM results "
                   "WHERE job_id=? AND tool=?", (job, "rnahybrid")).fetchall()

bad = ns = 0
for refseq, sym, a, b, extra in rows:
    e = json.loads(extra)
    strand = "".join(u if u != " " else p
                     for u, p in zip(e["target_unpaired"], e["target_paired"])
                     if (u + p).strip())
    got = seqs[refseq][a - 1:b]
    ns += strand.count("N")
    if len(strand) != len(got) or any(x != y and x != "N" for x, y in zip(strand, got)):
        bad += 1
        if bad <= 3:
            print("MISMATCH", sym, refseq, a, "-", b)
            print("   alignment:", strand)
            print("   sequence :", got)
print("checked", len(rows), " real mismatches", bad, " N placeholders", ns)
