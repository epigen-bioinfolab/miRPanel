"""Turning the stored `extra` JSON into flat, named columns.

The database keeps each tool's own fields as one JSON object, because the
fields differ per tool and a table cannot have a column for every tool's
private vocabulary. That is right for storage and wrong for every export:
JSON inside a TSV cell means an R user has to parse JSON per row to reach a
number, and a person opening the file sees a wall.

So exports flatten it. The result is sparse - a seed row has no TargetScan
family - but a labelled empty cell says "this tool does not report that",
which a JSON blob never could.
"""

# Promoted out of `extra` into real columns, in the order a reader wants
# them: the values people compare on first, the raw duplex strings last so
# everything readable sits in the leftmost columns.
EXTRA_ORDER = [
    # TargetScan
    "family", "family_conservation", "sites_conserved", "sites_nonconserved",
    "aggregate_pct", "in_default_set", "targetscan_transcript_is_mane",
    "seed_matches_current",
    # miRTarBase
    "status", "strong_functional", "weak_functional", "strong_nonfunctional",
    "weak_nonfunctional", "curated_sites", "pmids",
    # scanMiR - the per-transcript numbers first, then the per-site ones.
    # match_sequence is the KD model's 12-mer context window, wider than the
    # site's own coordinates, so it sits with the other raw strings at the end.
    "transcript_repression", "n_8mer_sites", "n_7mer_sites", "n_6mer_sites",
    "n_noncanonical_sites", "n_orf_canonical_sites", "n_orf_noncanonical_sites",
    "p3_score", "log_kd_scaled_int", "scanmir_orf_region", "site_note",
    # RNAhybrid - the four alignment strings are one picture of a duplex and
    # are only meaningful read together, so they go at the far right
    "duplex_span", "target_unpaired", "target_paired", "mirna_paired",
    "mirna_unpaired",
    "match_sequence",
]


def value(v):
    """One `extra` value as something a single cell can hold."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (list, tuple)):
        # PMIDs are the case that matters; ';' keeps them one searchable cell
        return "; ".join(str(x) for x in v)
    if isinstance(v, dict):
        import json
        return json.dumps(v, separators=(",", ":"))
    return v


def columns(base_cols, rows):
    """Base columns, then whichever extra keys these rows actually use.

    Unknown keys are kept rather than dropped - a tool that starts reporting
    something new should appear in the export without this file needing to be
    edited first - but they sort after the ones we know how to order.
    """
    seen = set()
    for r in rows:
        if r.get("extra"):
            seen.update(r["extra"].keys())
    known = [k for k in EXTRA_ORDER if k in seen]
    return list(base_cols) + known + sorted(seen - set(EXTRA_ORDER))


def rows_as_cells(rows, cols, base_cols):
    """Each row as a dict keyed by `cols`, with nothing left as JSON."""
    base = set(base_cols)
    out = []
    for r in rows:
        extra = r.get("extra") or {}
        out.append({c: (r.get(c) if c in base else value(extra.get(c)))
                    for c in cols})
    return out
