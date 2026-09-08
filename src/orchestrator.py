"""Create and run jobs. One job is one miRNA against a target set."""
import datetime, json, time, uuid
import resolve
import targets as T
from tools import registry

COLS = ("job_id", "mirna_acc", "mirna_name", "entrez", "symbol", "refseq",
        "region", "tool", "site_type", "pos_start", "pos_end", "score",
        "score_type", "low_confidence", "extra")

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")

def _tools(names=None):
    """The requested tool modules, or all of them."""
    every = registry.load()
    if names is None:
        return every
    missing = [n for n in names if n not in every]
    if missing:
        raise ValueError("unknown tools: %s" % missing)
    return {n: every[n] for n in names}

def _store(con, job_id, records):
    rows = [tuple([job_id] + [r[c] for c in COLS[1:]]) for r in records]
    con.executemany("INSERT INTO results VALUES (" + ",".join("?" * 15) + ")", rows)

def create_job(con, mirna_query, tools=None, genes=None, batch_id=None, opts=None):
    """Register one job. Raises if the miRNA cannot be resolved unambiguously."""
    m = resolve.resolve_mirna(con, mirna_query)
    if not m:
        raise ValueError("miRNA not found: %r" % mirna_query)
    if "accession" not in m:
        raise ValueError("miRNA is ambiguous: %r -> %r" % (mirna_query, m))
    job_id = "job_" + uuid.uuid4().hex[:12]
    params = {"mirna_query": mirna_query, "mirna_acc": m["accession"],
              "mirna_name": m["name"], "matched_by": m["matched_by"],
              "tools": list(tools) if tools else sorted(
                  n for n, mod in registry.load().items() if not mod.META["slow"]),
              "genes": list(genes) if genes else None, "opts": opts or {}}
    con.execute("INSERT INTO jobs (job_id, batch_id, created_at, status, params) "
                "VALUES (?,?,?,?,?)", (job_id, batch_id, now(), "queued",
                                       json.dumps(params)))
    con.commit()
    return job_id

def run_job(con, job_id, progress=None):
    """Run every requested tool. A failing tool is recorded, not fatal."""
    row = con.execute("SELECT params FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        raise ValueError("no such job: " + job_id)
    p = json.loads(row[0])
    con.execute("UPDATE jobs SET status='running', started_at=? WHERE job_id=?",
                (now(), job_id))
    con.execute("DELETE FROM results WHERE job_id=?", (job_id,))
    con.execute("DELETE FROM tool_runs WHERE job_id=?", (job_id,))
    con.commit()
    try:
        m = resolve.resolve_mirna(con, p["mirna_query"])
        tgts = T.targets_for(con, p["genes"]) if p.get("genes") else T.all_targets(con)
        total = 0
        for name, mod in _tools(p["tools"]).items():
            t0 = time.time()
            try:
                res = mod.run(con, m, tgts, p.get("opts"), progress)
                _store(con, job_id, res["records"])
                con.execute("INSERT OR REPLACE INTO tool_runs VALUES (?,?,?,?,?,?,?)",
                            (job_id, name, "ok", len(res["records"]),
                             round(time.time() - t0, 3),
                             json.dumps(res["provenance"]),
                             "; ".join(res["warnings"]) or None))
                total += len(res["records"])
            except Exception as exc:
                con.execute("INSERT OR REPLACE INTO tool_runs VALUES (?,?,?,?,?,?,?)",
                            (job_id, name, "failed", 0, round(time.time() - t0, 3),
                             None, repr(exc)))
            con.commit()
        con.execute("UPDATE jobs SET status='done', finished_at=?, n_results=? "
                    "WHERE job_id=?", (now(), total, job_id))
        con.commit()
        return total
    except Exception as exc:
        con.execute("UPDATE jobs SET status='failed', finished_at=?, error=? "
                    "WHERE job_id=?", (now(), repr(exc), job_id))
        con.commit()
        raise

def job_status(con, job_id):
    """Everything the API needs to report on a job."""
    j = con.execute("SELECT status, n_results, created_at, started_at, "
                    "finished_at, error, params FROM jobs WHERE job_id=?",
                    (job_id,)).fetchone()
    if j is None:
        return None
    runs = con.execute("SELECT tool, status, n_results, seconds, message "
                       "FROM tool_runs WHERE job_id=? ORDER BY tool",
                       (job_id,)).fetchall()
    return {"job_id": job_id, "status": j[0], "n_results": j[1],
            "created_at": j[2], "started_at": j[3], "finished_at": j[4],
            "error": j[5], "params": json.loads(j[6]),
            "tools": [{"tool": r[0], "status": r[1], "n_results": r[2],
                       "seconds": r[3], "message": r[4]} for r in runs]}
