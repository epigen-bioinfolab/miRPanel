"""Our own seed analyser, wrapped as a tool."""
import targets as T
from tools.registry import record
from tools.seed import find_sites

META = {"name": "seed", "version": "1.0", "kind": "prediction",
        "score_type": "site_type", "better": None,
        "categories": ["8mer", "7mer-m8", "7mer-A1", "6mer"],
        "gives_position": True, "needs_sequence": True, "slow": False}

SITE_LEN = {"6mer": 6, "7mer-A1": 7, "7mer-m8": 7, "8mer": 8}

def covers(con, entrez):
    """Seed analysis works on any transcript we hold."""
    return True

def run(con, mirna, tgts, opts=None, progress=None):
    """Scan every target transcript for seed sites."""
    opts = opts or {}
    refseqs = [t["refseq"] for t in tgts]
    seqs = T.sequences(con, refseqs)
    regs = T.regions(con, refseqs)
    out = []
    for i, t in enumerate(tgts, 1):
        seq = seqs.get(t["refseq"])
        if not seq:
            continue
        for s in find_sites(mirna["sequence"], seq, mirna["name"], t["refseq"]):
            stype = s["site_type"]
            start = s["position"] - (1 if stype in ("8mer", "7mer-m8") else 0)
            out.append(record(
                mirna, t, "seed",
                region=T.region_of(regs.get(t["refseq"], []), s["position"]),
                site_type=stype, pos_start=start,
                pos_end=start + SITE_LEN[stype] - 1,
                score_type="site_type", low_confidence=(stype == "6mer")))
        if progress and i % 4000 == 0:
            progress(i, len(tgts), "seed")
    return {"records": out,
            "provenance": {"tool": "seed", "version": META["version"], "params": {}},
            "warnings": []}
