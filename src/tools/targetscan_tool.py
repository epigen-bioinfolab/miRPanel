"""TargetScan v8.0 predictions, wrapped as a tool.

Gene-level only: for 38.7% of genes TargetScan's representative transcript
is not the MANE one, so no TargetScan position is ever reported.
"""
import json
from tools.registry import record

META = {"name": "targetscan", "version": "v8.0", "kind": "prediction",
        "score_type": "context++", "better": "lower",
        "gives_position": False, "needs_sequence": False, "slow": False}

def covers(con, entrez):
    """TargetScan covers a gene only if it appears in their gene table."""
    return con.execute("SELECT 1 FROM targetscan_genes WHERE entrez=?",
                       (entrez,)).fetchone() is not None

def run(con, mirna, tgts, opts=None, progress=None):
    """Look up every TargetScan prediction for this miRNA's seed family."""
    prov = {"tool": "targetscan", "version": "v8.0", "params": {}}
    ts = con.execute("SELECT seed, family, conservation FROM targetscan_mirnas "
                     "WHERE accession=?", (mirna["accession"],)).fetchone()
    if ts is None:
        return {"records": [], "provenance": prov,
                "warnings": ["miRNA is not in TargetScan v8.0"]}
    ts_seed, family, cons = ts
    prov["params"] = {"seed": ts_seed, "family": family}
    same = ts_seed == mirna["seed"]
    warn = [] if same else [
        "TargetScan used seed %s; miRBase R23 seed is %s" % (ts_seed, mirna["seed"])]
    by_entrez = {t["entrez"]: t for t in tgts}
    out = []
    for e, sc, sn, ctx, pct, dflt, mane in con.execute(
            "SELECT t.entrez, t.sites_conserved, t.sites_nonconserved, "
            "t.context_score, t.aggregate_pct, t.in_default, g.is_mane "
            "FROM targetscan t JOIN targetscan_genes g ON g.entrez=t.entrez "
            "WHERE t.seed=?", (ts_seed,)):
        t = by_entrez.get(e)
        if t is None:
            continue
        out.append(record(mirna, t, "targetscan", region="3UTR",
                          score=ctx, score_type="context++",
                          low_confidence=(sc == 0),
                          extra=json.dumps({
                              "family": family, "family_conservation": cons,
                              "sites_conserved": sc, "sites_nonconserved": sn,
                              "aggregate_pct": None if pct == 0 else pct,
                              "in_default_set": dflt,
                              "targetscan_transcript_is_mane": mane,
                              "seed_matches_current": same})))
    return {"records": out, "provenance": prov, "warnings": warn}
