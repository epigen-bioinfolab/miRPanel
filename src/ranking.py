"""How genes are ranked.

Shared by the API and the report so the two cannot disagree. The page shows
a page of genes in some order; the report takes the top N in that same
order. With a copy of the rule in each, a report headed "top 50 genes by
RNAhybrid" could quietly list different genes from the ones on screen under
the same sort, and nothing would catch it.

Direction is never assumed here either: it comes from each tool's own META,
the same rule the results endpoint enforces.
"""
from tools import registry


class BadSort(ValueError):
    """The requested sort cannot be honoured. The API turns this into a 422."""


def gene_order(sort):
    """SQL fragment and its bound arguments for ORDER BY, given a sort name."""
    metas = {m.META["name"]: m.META for m in registry.load().values()}
    if sort == "gene":
        return "symbol", []
    if sort == "seed":
        # a categorical tool has no number to sort on, so its own published
        # category order becomes the ranking - best first
        cats = metas["seed"]["categories"]
        case = " ".join("WHEN ? THEN %d" % (len(cats) - i)
                        for i in range(len(cats)))
        return ("MAX(CASE WHEN tool='seed' THEN (CASE site_type " + case +
                " ELSE 0 END) END) DESC, symbol"), list(cats)
    meta = metas.get(sort)
    if meta is None or meta["better"] is None:
        raise BadSort("sort must be 'gene', 'seed', or a tool with a "
                      "numeric score")
    # one gene has many sites, so a gene's rank is its best site: the lowest
    # score where lower is better, the highest where higher is
    agg = "MIN" if meta["better"] == "lower" else "MAX"
    expr = "%s(CASE WHEN tool=? THEN score END)" % agg
    direction = "ASC" if meta["better"] == "lower" else "DESC"
    return "%s IS NULL, %s %s, symbol" % (expr, expr, direction), [sort, sort]
