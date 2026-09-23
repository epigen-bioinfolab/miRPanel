"""The miRNA-target network: nodes and edges, built from stored results.

Nothing here is computed that the database does not already hold. A network
view is a second reading of the same rows, not a new analysis, so it must
never disagree with the table - it uses ranking.gene_order to pick the genes
and report.summarise to describe them, the same two functions the page and
the report use.

Two kinds of edge, and they mean different things:

  miRNA -> gene   this tool predicted or found evidence for this target.
                  Width is how many of the five tools agree, which is the
                  only honest cross-tool number available: their scores are
                  on different scales and are never combined.

  gene -- gene    these two genes appear together in enriched terms. This is
                  what turns a star into a picture: a bare miRNA-to-targets
                  graph shows nothing the table does not already say, while
                  genes clustered by shared biology show which targets belong
                  together.

The gene-gene layer needs a pathway analysis to exist. Without one the
network still draws, as a star, and says so rather than silently omitting a
layer the viewer might assume is there.
"""
import json

import ranking
import report

# A term containing most of your gene list links everything to everything and
# says nothing about which genes belong together - 20 list genes is 190 pairs
# on its own. Terms above this many of the tested genes are skipped for the
# gene-gene layer; they still appear everywhere else untouched.
TERM_SIZE_CAP = 12

# vis-network draws a few hundred edges comfortably and a few thousand as
# grey soup. Past this, the strongest pairings are kept and the rest dropped,
# with the count reported so the viewer knows it happened.
MAX_PAIR_EDGES = 400

TOOL_LABEL = {"seed": "seed analyser", "rnahybrid": "RNAhybrid",
              "targetscan": "TargetScan", "mirtarbase": "miRTarBase",
              "scanmir": "scanMiR"}


def _tools_for(rows):
    """Which tools reported anything at all for this gene, in a fixed order."""
    present = {r["tool"] for r in rows}
    return [t for t in ("seed", "rnahybrid", "targetscan", "mirtarbase",
                        "scanmir") if t in present]


def _gene_node(symbol, rows):
    """One gene as a node, carrying what the side panel shows on click."""
    g = report.summarise(rows)
    tools = _tools_for(rows)
    seed, rh, ts, mt = g["seed"], g["rh"], g["ts"], g["mt"]
    # summarise() predates scanMiR and ignores its rows, so the best site is
    # taken here. Lowest log Kd wins - the tool's own direction, the same
    # rule ranking.py uses, so the panel and the table agree.
    sm = [r for r in rows if r["tool"] == "scanmir"]
    best_sm = min(sm, key=lambda r: (r["score"] is None, r["score"])) \
        if sm else None
    mx = (mt or {}).get("extra") or {}
    strong = mx.get("strong_functional")
    return {
        "id": symbol,
        "label": symbol,
        # Validated is not a stronger prediction - it is a different kind of
        # claim, so it gets its own colour rather than a place on a scale.
        "group": "validated" if mt else "predicted",
        "value": len(tools),
        "entrez": g["entrez"],
        "refseq": g["refseq"],
        "tools": tools,
        "n_tools": len(tools),
        "regions": g["regions"],
        "seed_site": seed["site_type"] if seed else None,
        "n_seed": g["n_seed"],
        "dg": rh["score"] if rh else None,
        "n_rh": g["n_rh"],
        "context": ts["score"] if ts else None,
        "pct": ((ts or {}).get("extra") or {}).get("aggregate_pct"),
        "strong_functional": strong,
        "log_kd": best_sm["score"] if best_sm else None,
        "sm_site": best_sm["site_type"] if best_sm else None,
        "n_sm": len(sm),
    }


def _target_edges(nodes, mirna_id):
    out = []
    for n in nodes:
        out.append({
            "from": mirna_id, "to": n["id"], "kind": "target",
            "value": n["n_tools"],
            "tools": n["tools"],
            "title": "%s · found by %s" % (
                n["id"], ", ".join(TOOL_LABEL.get(t, t) for t in n["tools"])),
        })
    return out


def _shared_term_edges(con, run_id, symbols, min_shared, max_edges,
                       term_cap=TERM_SIZE_CAP):
    """Gene-gene edges from co-membership of enriched terms."""
    import enrichment as E

    shown = set(symbols)
    pairs, names, skipped = {}, {}, 0
    for t in E.terms(con, run_id, None, None, 0, None):
        members = sorted(m for m in (t["genes"] or "").split("/") if m in shown)
        if len(members) < 2:
            continue
        if len(members) > term_cap:
            skipped += 1
            continue
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                key = (a, b)
                pairs[key] = pairs.get(key, 0) + 1
                # keep a few term names for the tooltip, not all of them
                if len(names.setdefault(key, [])) < 4:
                    names[key].append(t["description"])
    ranked = sorted(((n, k) for k, n in pairs.items() if n >= min_shared),
                    key=lambda x: (-x[0], x[1]))
    dropped = max(0, len(ranked) - max_edges)
    out = []
    for n, (a, b) in ranked[:max_edges]:
        out.append({
            "from": a, "to": b, "kind": "shared_terms", "value": n,
            "shared": n, "terms": names[(a, b)],
            "title": "%s and %s share %d enriched term%s: %s" % (
                a, b, n, "" if n == 1 else "s", "; ".join(names[(a, b)])),
        })
    return out, {"pairs_found": len(pairs), "edges_dropped": dropped,
                 "terms_too_broad": skipped, "term_size_cap": term_cap}


def build(con, job_id, sort="gene", top_n=50, enrichment_run=None,
          min_shared=1, max_edges=MAX_PAIR_EDGES):
    """Everything the network panel needs, as one JSON-able dict."""
    import orchestrator

    st = orchestrator.job_status(con, job_id)
    if st is None:
        raise ValueError("no such job: " + job_id)
    order, oargs = ranking.gene_order(sort)
    total = con.execute("SELECT COUNT(DISTINCT symbol) FROM results "
                        "WHERE job_id=?", (job_id,)).fetchone()[0]
    syms = [r[0] for r in con.execute(
        "SELECT symbol FROM results WHERE job_id=? GROUP BY symbol "
        "ORDER BY " + order + " LIMIT ?", [job_id] + oargs + [int(top_n)])]

    nodes, by_gene = [], {}
    if syms:
        qs = ",".join("?" * len(syms))
        cols = ("symbol", "entrez", "refseq", "region", "tool", "site_type",
                "pos_start", "pos_end", "score", "score_type",
                "low_confidence", "extra")
        for r in con.execute("SELECT " + ", ".join(cols) + " FROM results "
                             "WHERE job_id=? AND symbol IN (" + qs + ")",
                             [job_id] + syms):
            d = dict(zip(cols, r))
            d["extra"] = json.loads(d["extra"]) if d["extra"] else None
            by_gene.setdefault(d["symbol"], []).append(d)
        nodes = [_gene_node(s, by_gene[s]) for s in syms if s in by_gene]

    p = st["params"]
    mirna_id = "mir:" + p["mirna_acc"]
    mirna_node = {"id": mirna_id, "label": p["mirna_name"], "group": "mirna",
                  "value": max(6, len(nodes) // 4),
                  "accession": p["mirna_acc"], "n_targets": len(nodes)}

    edges = _target_edges(nodes, mirna_id)

    # the newest completed run, unless the caller named one
    if enrichment_run is None:
        row = con.execute("SELECT run_id FROM enrichment_runs WHERE job_id=? "
                          "AND status='done' ORDER BY created_at DESC LIMIT 1",
                          (job_id,)).fetchone()
        enrichment_run = row[0] if row else None

    shared_stats, covered = None, 0
    if enrichment_run:
        pair_edges, shared_stats = _shared_term_edges(
            con, enrichment_run, [n["id"] for n in nodes], min_shared,
            max_edges)
        edges += pair_edges
        covered = len({n for e in pair_edges for n in (e["from"], e["to"])})

    return {
        "job_id": job_id,
        "mirna": {"name": p["mirna_name"], "accession": p["mirna_acc"]},
        "nodes": [mirna_node] + nodes,
        "edges": edges,
        "meta": {
            "sort": sort, "top_n": int(top_n),
            "genes_shown": len(nodes), "genes_total": total,
            "truncated": len(nodes) < total,
            "enrichment_run": enrichment_run,
            # said plainly rather than left for the viewer to infer from an
            # empty-looking graph
            "shared_layer": bool(enrichment_run),
            "genes_in_shared_layer": covered,
            "min_shared": min_shared,
            "shared_stats": shared_stats,
            "n_target_edges": sum(1 for e in edges if e["kind"] == "target"),
            "n_shared_edges": sum(1 for e in edges
                                  if e["kind"] == "shared_terms"),
        },
    }
