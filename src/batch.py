"""Run several miRNAs at once and compare their targets.

A batch is just a set of ordinary jobs sharing a batch_id. Nothing
downstream changes: each job has its own results table, binding map and
Venn, exactly as a single search does.

What a batch adds is the question you cannot ask with one miRNA: which
genes are targeted by several of them. A gene hit by four of five
changed miRNAs is a much stronger candidate than one hit by a single
miRNA, and that is usually what a differential-expression list is
asking about.
"""
import json

import orchestrator as O
import species as sp

#: Enough to cover a differential-expression result without letting one
#: request queue an hour of RNAhybrid.
MAX_MIRNAS = 20


def create(con, mirnas, tools=None, genes=None, species=None):
    """Queue one job per miRNA. Returns the batch id and the jobs."""
    names = []
    for m in mirnas:
        m = (m or "").strip()
        if m and m not in names:
            names.append(m)
    if not names:
        raise ValueError("no miRNA given")
    if len(names) > MAX_MIRNAS:
        raise ValueError("at most %d miRNAs per batch, %d given"
                         % (MAX_MIRNAS, len(names)))

    import uuid
    batch_id = "bat_" + uuid.uuid4().hex[:12]
    made, failed = [], []
    for name in names:
        try:
            jid = O.create_job(con, name, tools=tools, genes=genes,
                               species=species)
            con.execute("UPDATE jobs SET batch_id=? WHERE job_id=?",
                        (batch_id, jid))
            made.append({"mirna": name, "job_id": jid})
        except Exception as exc:
            # One bad name should not throw away the rest.
            failed.append({"mirna": name, "error": str(exc)})
    if not made:
        raise ValueError("no miRNA could be resolved: %s"
                         % "; ".join(f["error"] for f in failed))
    con.commit()
    return {"batch_id": batch_id, "jobs": made, "failed": failed}


def jobs(con, batch_id):
    """Every job in the batch, with its status."""
    out = []
    for jid, params, status, fin in con.execute(
            "SELECT job_id, params, status, finished_at FROM jobs "
            "WHERE batch_id=? ORDER BY created_at", (batch_id,)):
        p = json.loads(params)
        out.append({"job_id": jid,
                    "mirna": p.get("mirna_name") or p.get("mirna_query"),
                    "status": status, "finished_at": fin,
                    "species": O.job_species(p)})
    return out


def _where(site_types, tools):
    """Build the filter shared by every query here."""
    w, args = "", []
    if tools:
        w += " AND tool IN (%s)" % ",".join("?" * len(tools))
        args += list(tools)
    if site_types:
        w += " AND site_type IN (%s)" % ",".join("?" * len(site_types))
        args += list(site_types)
    return w, args


def gene_sets(con, batch_id, site_types=None, tools=None):
    """One set of target genes per miRNA."""
    w, args = _where(site_types, tools)
    out = {}
    for j in jobs(con, batch_id):
        rows = con.execute(
            "SELECT DISTINCT entrez, symbol FROM results WHERE job_id=?" + w,
            [j["job_id"]] + args).fetchall()
        out[j["mirna"]] = {e: s for e, s in rows}
    return out


def intersection(con, batch_id, min_count=None, site_types=None, tools=None):
    """Genes targeted by several miRNAs in the batch.

    min_count defaults to all of them. Lower it to see genes shared by
    most but not quite every miRNA, which is usually the more useful
    list.
    """
    sets = gene_sets(con, batch_id, site_types, tools)
    if not sets:
        return {"batch_id": batch_id, "min_count": 0, "n_mirnas": 0,
                "genes": [], "per_mirna": {}}

    n = len(sets)
    min_count = int(min_count or n)
    min_count = max(1, min(min_count, n))

    hits, names = {}, {}
    for mir, genes in sets.items():
        for e, s in genes.items():
            hits.setdefault(e, []).append(mir)
            names[e] = s

    out = [{"entrez": e, "symbol": names.get(e), "n_mirnas": len(ms),
            "mirnas": sorted(ms)}
           for e, ms in hits.items() if len(ms) >= min_count]
    out.sort(key=lambda r: (-r["n_mirnas"], r["symbol"] or ""))

    return {"batch_id": batch_id,
            "n_mirnas": n,
            "min_count": min_count,
            "per_mirna": {m: len(g) for m, g in sets.items()},
            "n_genes": len(out),
            "genes": out}
