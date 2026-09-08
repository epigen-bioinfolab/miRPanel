"""Create and run one job, then print a preview of the results."""
import sqlite3, sys
sys.path.insert(0, "src")
import orchestrator as O
import resolve

DB = "data/processed/mirna.db"
args = sys.argv[1:]
tools = None
if "--tools" in args:
    i = args.index("--tools")
    tools = args[i + 1].split(",")
    del args[i:i + 2]
mir = args[0] if args else "hsa-miR-21-5p"
gene_args = args[1:]

con = sqlite3.connect(DB)
genes = None
if gene_args:
    genes = []
    for g in gene_args:
        r = resolve.resolve_gene(con, g)
        if not r or "entrez" not in r:
            sys.exit("gene not resolved: " + g)
        genes.append(r["entrez"])

def show(done, total, tool):
    print("   %s %d/%d" % (tool, done, total))

job = O.create_job(con, mir, tools=tools, genes=genes)
print("job", job)
O.run_job(con, job, progress=show)
st = O.job_status(con, job)
print("miRNA :", st["params"]["mirna_name"], st["params"]["mirna_acc"],
      "(%s)" % st["params"]["matched_by"])
print("status:", st["status"], " results:", st["n_results"])
for t in st["tools"]:
    print("  %-11s %-6s %7d rows  %6.2fs  %s" %
          (t["tool"], t["status"], t["n_results"], t["seconds"] or 0,
           t["message"] or ""))

print()
print("genes with an 8mer (first 5), every tool:")
top = [r[0] for r in con.execute(
    "SELECT DISTINCT entrez FROM results WHERE job_id=? AND site_type='8mer' "
    "ORDER BY symbol LIMIT 5", (job,))]
for e in top:
    for sym, tool, region, stype, ps, score, sct in con.execute(
            "SELECT symbol, tool, region, site_type, pos_start, score, score_type "
            "FROM results WHERE job_id=? AND entrez=? ORDER BY tool, pos_start",
            (job, e)):
        print("  %-10s %-11s %-5s %-8s %7s  %8s %s" % (
            sym, tool, region or "-", stype or "-",
            "-" if ps is None else ps,
            "-" if score is None else round(score, 3), sct or ""))
    print()
