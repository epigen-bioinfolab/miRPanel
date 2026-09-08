"""Print the status of a job, or of the most recent one."""
import sqlite3, sys
sys.path.insert(0, "src")
import orchestrator as O

con = sqlite3.connect("data/processed/mirna.db")
con.execute("PRAGMA busy_timeout = 15000")
job = sys.argv[1] if len(sys.argv) > 1 else con.execute(
    "SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()[0]
st = O.job_status(con, job)
if st is None:
    sys.exit("no such job: " + job)
print(job, st["status"], " results:", st["n_results"])
print("  miRNA   :", st["params"]["mirna_name"], st["params"]["mirna_acc"])
print("  tools   :", ",".join(st["params"]["tools"]))
print("  created :", st["created_at"], " started:", st["started_at"],
      " finished:", st["finished_at"])
if st["error"]:
    print("  error   :", st["error"])
for t in st["tools"]:
    print("  %-11s %-6s %7d rows %8.2fs %s" %
          (t["tool"], t["status"], t["n_results"], t["seconds"] or 0,
           t["message"] or ""))
