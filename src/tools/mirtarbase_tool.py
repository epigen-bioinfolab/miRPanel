"""miRTarBase 10.0 experimental evidence, wrapped as a tool.

This is evidence, not prediction. Non-Functional MTI records a published
finding that the miRNA does NOT regulate the gene and is never presented
as validation.
"""
import json
from tools.registry import record

META = {"name": "mirtarbase", "version": "10.0", "kind": "evidence",
        "score_type": "strong functional experiments", "better": "higher",
        "gives_position": False, "needs_sequence": False, "slow": False}

def covers(con, entrez):
    """Every gene is covered: no record is itself a meaningful answer (novel)."""
    return True

def run(con, mirna, tgts, opts=None, progress=None):
    """Fetch the experimental record for this miRNA against every target."""
    by_entrez = {t["entrez"]: t for t in tgts}
    out = []
    for e, sf, wf, sn, wn, ns, pm in con.execute(
            "SELECT entrez, n_strong_func, n_weak_func, n_strong_nonfunc, "
            "n_weak_nonfunc, n_sites, pmids FROM mirtarbase WHERE accession=?",
            (mirna["accession"],)):
        t = by_entrez.get(e)
        if t is None:
            continue
        status = ("validated_strong" if sf else
                  "reported_weak" if wf else "evidence_of_no_effect")
        out.append(record(mirna, t, "mirtarbase",
                          score=float(sf), score_type=META["score_type"],
                          low_confidence=(sf == 0),
                          extra=json.dumps({
                              "status": status,
                              "strong_functional": sf, "weak_functional": wf,
                              "strong_nonfunctional": sn, "weak_nonfunctional": wn,
                              "curated_sites": ns,
                              "pmids": [p for p in (pm or "").split(",") if p][:20]})))
    return {"records": out,
            "provenance": {"tool": "mirtarbase", "version": "10.0", "params": {}},
            "warnings": []}
