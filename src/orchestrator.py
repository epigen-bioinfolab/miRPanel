"""Create and run jobs. One job is one miRNA against a target set.

A job now belongs to exactly one species. That species is resolved
once, at create time, and stored in the job's `params` JSON - the
`jobs` table needs no new column because `params` is already JSON.
Storing it rather than re-deriving it matters: a job must mean the
same thing when it is re-read months later for a report.

Jobs created before multi-species have no `species` key, so every
read falls back to human. Those jobs keep reporting exactly what they
reported before.
"""
import datetime, json, time, uuid
import resolve
import species as sp
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


def _pick_tools(requested, species, every):
    """Which tools to run, and why any were left out.

    Two different situations, deliberately handled differently:

    - the user NAMED a tool this species has no data for: raise, so
      they find out now instead of reading an empty column and
      wondering whether the tool found nothing or never ran. "no
      sites" and "not available" are different answers.

    - the user took the defaults: silently omit the unavailable ones
      and record the reason on the job, so the page can say why a
      column is missing without the job having failed.
    """
    if requested:
        unknown = [n for n in requested if n not in every]
        if unknown:
            raise ValueError("unknown tools: %s" % unknown)
        blocked = [(n, sp.unsupported_reason(species, n))
                   for n in requested if not sp.supports(species, n)]
        if blocked:
            raise ValueError("; ".join(r for _, r in blocked))
        return list(requested), []

    chosen = sorted(n for n, mod in every.items()
                    if not mod.META["slow"] and sp.supports(species, n))
    dropped = [{"tool": n, "reason": sp.unsupported_reason(species, n)}
               for n in sorted(every) if not sp.supports(species, n)]
    return chosen, dropped


def create_job(con, mirna_query, tools=None, genes=None, batch_id=None,
               opts=None, species=sp.DEFAULT):
    """Register one job. Raises if the miRNA cannot be resolved unambiguously."""
    sp.get(species)
    m = resolve.resolve_mirna(con, mirna_query, species)
    if not m:
        raise ValueError("miRNA not found: %r" % mirna_query)
    if "accession" not in m:
        raise ValueError("miRNA is ambiguous: %r -> %r" % (mirna_query, m))

    # A miRNA from another organism is allowed but flagged. Seeds are
    # often conserved and scanning one species' miRNA against
    # another's transcriptome is a real experiment, so refusing would
    # block legitimate work. Usually, though, it is a mistake - so it
    # is recorded on the job and the page can say so.
    warnings = []
    if not sp.prefix_ok(species, m["name"]):
        warnings.append(
            "%s is not a %s miRNA; it is being scanned against %s "
            "transcripts" % (m["name"], sp.get(species)["common"].lower(),
                             sp.get(species)["common"].lower()))

    if genes:
        resolved, bad = [], []
        for g in genes:
            r = resolve.resolve_gene(con, str(g), species)
            (resolved.append(r["entrez"]) if r and "entrez" in r
             else bad.append(g))
        if bad:
            raise ValueError("genes not found in %s: %s"
                             % (sp.get(species)["common"].lower(), bad))
        have = {t["entrez"] for t in T.targets_for(con, resolved, species)}
        missing = [g for g, e in zip(genes, resolved) if e not in have]
        if missing:
            raise ValueError("no canonical transcript for: %s" % missing)
        genes = resolved

    every = registry.load()
    chosen, dropped = _pick_tools(tools, species, every)

    job_id = "job_" + uuid.uuid4().hex[:12]
    params = {"species": species,
              "mirna_query": mirna_query, "mirna_acc": m["accession"],
              "mirna_name": m["name"], "matched_by": m["matched_by"],
              "tools": chosen,
              "tools_unavailable": dropped,
              "warnings": warnings,
              "genes": list(genes) if genes else None, "opts": opts or {}}
    con.execute("INSERT INTO jobs (job_id, batch_id, created_at, status, params) "
                "VALUES (?,?,?,?,?)", (job_id, batch_id, now(), "queued",
                                       json.dumps(params)))
    con.commit()
    return job_id


def job_species(params):
    """The species of a job. Pre-multi-species jobs are human."""
    return params.get("species") or sp.DEFAULT


def run_job(con, job_id, progress=None):
    """Run every requested tool. A failing tool is recorded, not fatal."""
    row = con.execute("SELECT params FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        raise ValueError("no such job: " + job_id)
    p = json.loads(row[0])
    species = job_species(p)
    con.execute("UPDATE jobs SET status='running', started_at=? WHERE job_id=?",
                (now(), job_id))
    con.execute("DELETE FROM results WHERE job_id=?", (job_id,))
    con.execute("DELETE FROM tool_runs WHERE job_id=?", (job_id,))
    con.commit()
    try:
        m = resolve.resolve_mirna(con, p["mirna_query"], species)
        tgts = (T.targets_for(con, p["genes"], species) if p.get("genes")
                else T.all_targets(con, species))
        if not tgts:
            raise ValueError("no %s target transcripts for job %s"
                             % (species, job_id))
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
    params = json.loads(j[6])
    return {"job_id": job_id, "status": j[0], "n_results": j[1],
            "created_at": j[2], "started_at": j[3], "finished_at": j[4],
            "error": j[5], "params": params,
            "species": job_species(params),
            "tools": [{"tool": r[0], "status": r[1], "n_results": r[2],
                       "seconds": r[3], "message": r[4]} for r in runs]}


def next_queued(con):
    """Atomically claim the oldest queued job. Returns job_id, or None."""
    row = con.execute("SELECT job_id FROM jobs WHERE status='queued' "
                      "ORDER BY created_at LIMIT 1").fetchone()
    if row is None:
        return None
    cur = con.execute("UPDATE jobs SET status='running', started_at=? "
                      "WHERE job_id=? AND status='queued'", (now(), row[0]))
    con.commit()
    return row[0] if cur.rowcount else None


def requeue_stale(con):
    """Put jobs left 'running' by a crashed worker back in the queue."""
    cur = con.execute("UPDATE jobs SET status='queued', started_at=NULL "
                      "WHERE status='running'")
    con.commit()
    return cur.rowcount
