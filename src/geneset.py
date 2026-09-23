"""Turn the pathway-analysis tick boxes into a set of genes.

Each ticked box becomes one set of Entrez ids drawn from a job's results.
The sets are then combined with AND (intersection) or OR (union). Nothing
here invents a threshold: every number comes from the caller, and the rule
that produced the set is returned in words so the report can state it.
"""
import json

from tools import registry

REGIONS = ("5UTR", "CDS", "3UTR")
POSITIONAL = ("seed", "rnahybrid")     # the only tools a region filter can apply to


def site_types(minimum):
    """Site types at least as good as `minimum`, best first, from the
    registry's own ranking. Never hard-coded here."""
    cats = list(registry.load(["seed_tool"])["seed"].META["categories"])
    if minimum in (None, "", "any"):
        return cats
    if minimum not in cats:
        raise ValueError("unknown site type %r; expected one of %s"
                         % (minimum, cats))
    return cats[:cats.index(minimum) + 1]


def _genes(con, job_id, where, args):
    return {r[0] for r in con.execute(
        "SELECT DISTINCT entrez FROM results WHERE job_id=? AND " + where,
        [job_id] + args)}


def _region_clause(regions):
    """Only applied to tools that report a position."""
    if not regions or set(regions) == set(REGIONS):
        return "", []
    bad = [r for r in regions if r not in REGIONS]
    if bad:
        raise ValueError("unknown region %s; expected %s" % (bad, list(REGIONS)))
    return " AND region IN (%s)" % ",".join("?" * len(regions)), list(regions)


def select(con, job_id, spec):
    """spec keys, all optional:
         seed        '8mer' | '7mer-m8' | '7mer-A1' | '6mer' | 'any'
         targetscan  'any' | 'conserved' | a number (context++ at most this)
         rnahybrid   a number (dG at most this)
         mirtarbase  'strong'
         regions     list, applied to seed and rnahybrid only
         match       'all' (AND, default) or 'any' (OR)
         genes       an explicit list of Entrez ids - bypasses every rule
                     above. For a set someone already has, such as one
                     exclusive region of the agreement diagram: the genes
                     were chosen by a click, not by a rule this function
                     could write in words, so the caller supplies its own
                     sentence (enrichment.create() does this for a click).
    Returns the gene ids, the count, and each rule written out in words.
    """
    if spec.get("genes") is not None:
        genes = sorted(set(int(g) for g in spec["genes"]))
        return {"genes": genes, "count": len(genes), "rules": [],
                "match": spec.get("match") or "all",
                "sentence": "%d gene%s" % (len(genes),
                                           "" if len(genes) == 1 else "s")}

    match = (spec.get("match") or "all").lower()
    if match not in ("all", "any"):
        raise ValueError("match must be 'all' or 'any'")
    regions = spec.get("regions") or list(REGIONS)
    rclause, rargs = _region_clause(regions)
    inreg = "" if not rclause else " in " + " or ".join(
        {"5UTR": "the 5'UTR", "CDS": "the CDS", "3UTR": "the 3'UTR"}[r]
        for r in regions)

    sets, rules = [], []

    if spec.get("seed"):
        types = site_types(spec["seed"])
        qs = ",".join("?" * len(types))
        sets.append(_genes(con, job_id,
                           "tool='seed' AND site_type IN (%s)%s" % (qs, rclause),
                           types + rargs))
        label = types[0] if len(types) == 1 else "%s or better" % types[-1]
        rules.append("%s %s site%s" % ("an" if label[0] in "8aeiou" else "a",
                                       label, inreg))

    ts = spec.get("targetscan")
    if ts:
        if ts == "any":
            sets.append(_genes(con, job_id, "tool='targetscan'", []))
            rules.append("scored by TargetScan")
        elif ts == "conserved":
            sets.append(_genes(con, job_id,
                               "tool='targetscan' AND low_confidence=0", []))
            rules.append("a conserved TargetScan site")
        else:
            cut = float(ts)
            sets.append(_genes(con, job_id,
                               "tool='targetscan' AND score <= ?", [cut]))
            rules.append("TargetScan context++ at most %s" % cut)

    if spec.get("rnahybrid") not in (None, ""):
        cut = float(spec["rnahybrid"])
        sets.append(_genes(con, job_id,
                           "tool='rnahybrid' AND score <= ?%s" % rclause,
                           [cut] + rargs))
        rules.append("an RNAhybrid duplex at most %s kcal/mol%s" % (cut, inreg))

    if spec.get("mirtarbase"):
        sets.append(_genes(con, job_id,
                           "tool='mirtarbase' AND score > 0", []))
        rules.append("strong experimental support in miRTarBase")

    if not sets:
        return {"genes": [], "count": 0, "rules": [], "match": match,
                "sentence": "no filter selected"}

    out = set(sets[0])
    for s in sets[1:]:
        out = (out & s) if match == "all" else (out | s)

    joiner = " and " if match == "all" else " or "
    sentence = "%d gene%s with %s" % (len(out), "" if len(out) == 1 else "s",
                                      joiner.join(rules))
    return {"genes": sorted(out), "count": len(out), "rules": rules,
            "match": match, "sentence": sentence}
