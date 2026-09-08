"""The contract every tool follows.

A tool module defines:
    META                  describes the tool (see REQUIRED_META)
    covers(con, entrez)   True if the tool can say anything about this gene
    run(con, mirna, targets, opts, progress=None)
                          -> {"records": [...], "provenance": {...},
                              "warnings": [...]}

Every position in a record is 1-based on the MANE transcript.
Scores are never comparable between tools; score_type names the units.
"""
import importlib

REQUIRED_META = ("name", "version", "kind", "score_type", "better",
                 "gives_position", "needs_sequence", "slow")

DEFAULT_TOOLS = ("seed_tool", "targetscan_tool", "mirtarbase_tool", "rnahybrid_tool")

def check_meta(meta):
    """Reject a tool whose META is incomplete or contradictory."""
    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        raise ValueError("tool META missing %s" % missing)
    if meta["kind"] not in ("prediction", "evidence"):
        raise ValueError("kind must be prediction or evidence: %r" % meta["kind"])
    if meta["better"] not in ("lower", "higher", None):
        raise ValueError("better must be lower/higher/None: %r" % meta["better"])
    if meta["better"] is None:
        cats = meta.get("categories")
        if not isinstance(cats, (list, tuple)) or len(cats) < 2:
            raise ValueError(
                "a categorical tool must publish 'categories', best first: %r"
                % meta["name"])
    return meta

def load(names=DEFAULT_TOOLS):
    """Import the tool modules and return {tool name: module}."""
    out = {}
    for mod in names:
        m = importlib.import_module("tools." + mod)
        check_meta(m.META)
        out[m.META["name"]] = m
    return out

def record(mirna, target, tool, **kw):
    """Build one standardised result record."""
    return {"mirna_acc": mirna["accession"], "mirna_name": mirna["name"],
            "entrez": target["entrez"], "symbol": target["symbol"],
            "refseq": target.get("refseq"), "region": kw.get("region"),
            "tool": tool, "site_type": kw.get("site_type"),
            "pos_start": kw.get("pos_start"), "pos_end": kw.get("pos_end"),
            "score": kw.get("score"), "score_type": kw.get("score_type"),
            "low_confidence": int(bool(kw.get("low_confidence", 0))),
            "extra": kw.get("extra")}
