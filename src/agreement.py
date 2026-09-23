"""Which tools agree on which genes.

The results table answers "what did each tool find". This answers the question
underneath it: how much do the tools actually overlap, and which genes sit in
the parts where they disagree.

Two ideas keep it honest.

**A set is a decision, not a fact.** "scanMiR found this gene" is only
meaningful once you say what counts as finding it. At its default threshold
scanMiR reports at least one site on 88% of the transcriptome, so counting any
site would give it a circle that swallows every other set and a diagram that
says nothing. Its set is therefore canonical sites only, which puts it in the
same order of magnitude as TargetScan. The rule travels with the result, in
`membership`, so a figure can state it.

**Regions are exclusive.** A gene counted in "seed AND TargetScan" is found by
those two and by nothing else in the selection. That is what a Venn region
means, and it is what makes the region sizes sum to the total.

Computed per request, like the network view: it is one indexed read and some
counting. Nothing is stored, because nothing here is new.
"""
import itertools
import json

from tools import registry

# Display names, kept in one place so the figure, the enrichment sentence it
# can trigger, and any export all say the same thing about the same tool.
TOOLLABEL = {"seed": "Seed analyser", "rnahybrid": "RNAhybrid",
             "targetscan": "TargetScan", "mirtarbase": "miRTarBase",
             "scanmir": "scanMiR"}


def _nice(t):
    return TOOLLABEL.get(t, t)


def region_label(inc, exc):
    """'by seed and TargetScan, and not by RNAhybrid or miRTarBase' - the
    fragment naming one exclusive region. Shared by the figure's own labels
    and by an enrichment run started from a click on one, so a region and
    the run it started can never describe the same genes two different ways.
    """
    if not inc:
        return "by no tool"
    names = [_nice(t) for t in inc]
    who = names[0] if len(names) == 1 else (
        ", ".join(names[:-1]) + " and " + names[-1])
    out = "by " + who
    if exc:
        onames = [_nice(t) for t in exc]
        out += ", and not by " + (onames[0] if len(onames) == 1 else
                                  ", ".join(onames[:-1]) + " or " + onames[-1])
    return out


def describe_region(inc, exc, tools_meta):
    """One sentence about what a region *means*, not just which tools they
    are. Evidence and prediction are different kinds of information (see the
    module docstring), so a region that mixes them says so."""
    evid = [t for t in inc if tools_meta.get(t, {}).get("kind") == "evidence"]
    pred = [t for t in inc if tools_meta.get(t, {}).get("kind") == "prediction"]
    sent = "Found " + region_label(inc, exc) + "."
    if evid and pred:
        sent += (" Computational prediction corroborated by published "
                "experimental evidence.")
    elif evid and not pred:
        sent += (" Experimental evidence with no computational prediction "
                "backing it under these filters.")
    elif len(pred) > 1:
        sent += (" Independent computational agreement, with no "
                "experimental record yet.")
    return sent


# scanMiR site classes that count towards set membership. Everything else -
# the 6mer family and the non-canonical tail, 76% of its sites for miR-21 -
# is real output and stays in the table, but is too permissive to define a
# set by. See manifests/scanmir_design.md, finding 4.
SCANMIR_CANONICAL = ("8mer", "7mer-m8", "7mer-a1", "7mer-A1",
                     "wobbled 8mer", "wobbled 7mer",
                     "g-bulged 8mer", "g-bulged 7mer")

# Above this many sets a Venn needs ellipses and 31 regions, several too thin
# to click. The caller is told which shape to draw rather than guessing.
VENN_MAX_SETS = 4


class BadRequest(ValueError):
    """The caller asked for something that cannot be answered. -> 422."""


def _membership_sql(scanmir_canonical):
    """Extra WHERE terms that turn rows into set membership."""
    if not scanmir_canonical:
        return "", []
    qs = ",".join("?" * len(SCANMIR_CANONICAL))
    return (" AND NOT (tool = 'scanmir' AND (site_type IS NULL "
            "OR site_type NOT IN (%s)))" % qs), list(SCANMIR_CANONICAL)


def _sets(con, job_id, where, args, tools, scanmir_canonical):
    """{tool: {entrez}} and {entrez: symbol}, after filters."""
    extra, extra_args = _membership_sql(scanmir_canonical)
    sql = ("SELECT DISTINCT entrez, symbol, tool FROM results WHERE "
           + where + extra)
    a = list(args) + extra_args
    if tools:
        sql += " AND tool IN (" + ",".join("?" * len(tools)) + ")"
        a += list(tools)
    sets, names = {}, {}
    for entrez, symbol, tool in con.execute(sql, a):
        sets.setdefault(tool, set()).add(entrez)
        names[entrez] = symbol
    return sets, names


def build(con, job_id, tools=None, where=None, args=None,
          scanmir_canonical=True, filters=None):
    """Set sizes and every non-empty exclusive region.

    `where`/`args` come from the caller's own filter builder, so the diagram
    is computed over exactly the rows the table is showing. A figure whose
    numbers disagree with the table above it reads as a bug even when both
    are right.
    """
    if where is None:
        where, args = "job_id = ?", [job_id]
    ran = [r[0] for r in con.execute(
        "SELECT tool FROM tool_runs WHERE job_id=? AND status='ok' "
        "ORDER BY tool", (job_id,))]
    if not ran:
        raise BadRequest("job %s has no completed tool runs" % job_id)

    if tools:
        unknown = [t for t in tools if t not in ran]
        if unknown:
            raise BadRequest("these tools did not run in this job: %s"
                             % ", ".join(unknown))
    else:
        tools = ran
    if len(tools) < 1:
        raise BadRequest("an agreement diagram needs at least one tool")

    sets, names = _sets(con, job_id, where, args, tools, scanmir_canonical)
    sets = {t: sets.get(t, set()) for t in tools}

    # Every gene in at least one set, assigned to exactly one region.
    regions = {}
    for entrez in set().union(*sets.values()) if sets else set():
        key = tuple(t for t in tools if entrez in sets[t])
        regions[key] = regions.get(key, 0) + 1

    metas = {m.META["name"]: m.META for m in registry.load().values()}
    total = len(names) or 1  # percentages of the union; guard the 0-gene case

    def _region(k, n):
        inc, exc = list(k), [t for t in tools if t not in k]
        return {"in": inc, "out": exc, "n": n,
                "pct": round(100.0 * n / total, 1),
                "label": region_label(inc, exc),
                "note": describe_region(inc, exc, metas)}

    # Every non-empty combination of the picked tools gets a region, whether
    # or not any gene actually landed there. A Venn is read by its shape as
    # much as its numbers - a slice silently missing because it happened to
    # be empty reads as the figure being broken, not as "zero". Sum over the
    # shown regions is still exactly 100%; the empty ones just contribute 0.
    all_keys = [k for r in range(1, len(tools) + 1)
                for k in itertools.combinations(tools, r)]

    # One circle needs no overlap geometry; up to four draw as a real Venn;
    # past that a Venn needs ellipses and 31 regions, several too thin to
    # click, so the frontend switches to an UpSet-style list instead.
    if len(tools) == 1:
        display = "single"
    elif len(tools) <= VENN_MAX_SETS:
        display = "venn"
    else:
        display = "upset"

    return {
        "job_id": job_id,
        "tools": [{"tool": t,
                   "n_genes": len(sets[t]),
                   "kind": metas.get(t, {}).get("kind"),
                   # miRTarBase is published evidence, not prediction. Its
                   # overlap with a predictor means something different from
                   # two predictors overlapping, and the figure should show
                   # that rather than imply five equivalent methods.
                   "is_evidence": metas.get(t, {}).get("kind") == "evidence"}
                  for t in tools],
        "regions": sorted(
            (_region(k, regions.get(k, 0)) for k in all_keys),
            key=lambda r: (-len(r["in"]), -r["n"])),
        "n_genes": len(names),
        "display": display,
        "membership": {
            "rule": "a gene is in a tool's set if that tool reported at "
                    "least one row for it, after the filters below",
            "scanmir_canonical_only": bool(scanmir_canonical),
            "scanmir_site_types": list(SCANMIR_CANONICAL)
            if scanmir_canonical else None},
        "filters": filters or {},
    }


def region_genes(con, job_id, inc, exc, where=None, args=None,
                 scanmir_canonical=True, limit=100, offset=0):
    """The genes in one exclusive region, with what each tool said about them.

    `inc` are the tools a gene must be in, `exc` the tools it must not be in.
    Both are needed: "found by seed and TargetScan" and "found by seed and
    TargetScan and nothing else" are different sets, and clicking a Venn
    region means the second.
    """
    if where is None:
        where, args = "job_id = ?", [job_id]
    inc, exc = list(inc or []), list(exc or [])
    if not inc:
        raise BadRequest("a region must include at least one tool")

    sets, names = _sets(con, job_id, where, args, inc + exc,
                        scanmir_canonical)
    keep = set(names)
    for t in inc:
        keep &= sets.get(t, set())
    for t in exc:
        keep -= sets.get(t, set())

    ordered = sorted(keep, key=lambda e: (names.get(e) or "", e))
    total = len(ordered)
    page = ordered[offset:offset + limit]
    if not page:
        return {"job_id": job_id, "in": inc, "out": exc,
                "n_genes": total, "genes": []}

    metas = {m.META["name"]: m.META for m in registry.load().values()}
    qs = ",".join("?" * len(page))
    rows = con.execute(
        "SELECT entrez, symbol, refseq, tool, region, site_type, pos_start, "
        "score, score_type, low_confidence, extra FROM results WHERE " + where +
        " AND entrez IN (" + qs + ")", list(args) + page).fetchall()

    per = {e: {} for e in page}
    regions = {e: set() for e in page}
    for entrez, symbol, refseq, tool, region, stype, pos, score, sct, low, \
            extra in rows:
        if entrez not in per:
            continue
        if region:
            regions[entrez].add(region)
        d = per[entrez].setdefault(
            tool, {"n_sites": 0, "best_score": None, "best_site_type": None,
                   "score_type": sct, "best_position": None, "status": None,
                   "_rank": None})
        d["n_sites"] += 1

        # "Best" is the tool's own rule, never a guess - the same rule
        # ranking.py applies, so a gene's headline here and on the results
        # page cannot disagree.
        #
        # A numeric tool ranks by its score in its own direction. A
        # categorical tool has no number, so its published category order
        # becomes the ranking, best first. Without that branch the panel
        # showed whichever site came back first: PDCD4's seed row read
        # "6mer" while an 8mer sat at position 1805.
        meta = metas.get(tool, {})
        better, cats = meta.get("better"), meta.get("categories")
        rank = None
        if better in ("lower", "higher") and score is not None:
            rank = score if better == "lower" else -score
        elif cats and stype in cats:
            rank = cats.index(stype)
        if rank is not None and (d["_rank"] is None or rank < d["_rank"]):
            d["_rank"] = rank
            d["best_score"] = score
            d["best_site_type"] = stype
            d["best_position"] = pos
        elif d["best_site_type"] is None and stype:
            # an unknown category: keep something rather than nothing, but
            # never let it displace a properly ranked site
            d["best_site_type"] = stype
            d["best_position"] = pos

        if tool == "mirtarbase" and extra:
            try:
                d["status"] = json.loads(extra).get("status")
            except (ValueError, TypeError):
                pass

    for g in per.values():
        for d in g.values():
            d.pop("_rank", None)

    return {
        "job_id": job_id, "in": inc, "out": exc,
        "n_genes": total, "offset": offset, "limit": limit,
        "genes": [{"entrez": e, "symbol": names.get(e),
                   "regions": sorted(regions[e]),
                   "tools": per[e]} for e in page],
    }
