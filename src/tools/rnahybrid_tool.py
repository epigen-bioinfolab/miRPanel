"""RNAhybrid 2.1.2-8, wrapped as a tool.

Rules established by the spike (manifests/rnahybrid_spike.md):
  - FASTA must be line-wrapped; one long line silently loses a nucleotide
  - -m must be at least the longest target, or the run aborts with no output
  - -f 2,7 forces seed pairing; without it thermodynamic decoys outrank sites
  - the reported target length is checked against ours; a mismatch is fatal
  - mfe 0.0 at position 0 means no hit, not a perfect hit
  - the p-value depends on target length and is never stored
"""
import json, os, shutil, subprocess, tempfile
import targets as T
from tools.registry import record

META = {"name": "rnahybrid", "version": "2.1.2-8", "kind": "prediction",
        "score_type": "MFE kcal/mol", "better": "lower",
        "gives_position": True, "needs_sequence": True, "slow": True}

BIN = "RNAhybrid"

def covers(con, entrez):
    """Any transcript we hold can be folded."""
    return True

def _wrap(seq, n=60):
    return "\n".join(seq[i:i + n] for i in range(0, len(seq), n))

def _span(a1, a2):
    """Target nucleotides spanned by the duplex: non-gap columns of both rows."""
    return sum(1 for c in a1 if c != " ") + sum(1 for c in a2 if c != " ")

def _parse(text, mirna, by_refseq, seqs, regs):
    """Compact RNAhybrid output -> standard records."""
    out = []
    for line in text.splitlines():
        f = line.split(":")
        if len(f) < 11:
            continue
        refseq, tlen, mfe, pos = f[0], int(f[1]), float(f[4]), int(f[6])
        if pos == 0 and mfe == 0.0:
            continue
        if tlen != len(seqs[refseq]):
            raise RuntimeError("RNAhybrid read %s as %d nt, we supplied %d"
                               % (refseq, tlen, len(seqs[refseq])))
        span = _span(f[7], f[8])
        out.append(record(mirna, by_refseq[refseq], "rnahybrid",
                          region=T.region_of(regs.get(refseq, []), pos),
                          pos_start=pos, pos_end=pos + span - 1,
                          score=mfe, score_type=META["score_type"],
                          low_confidence=(mfe > -20.0),
                          extra=json.dumps({"target_unpaired": f[7],
                                            "target_paired": f[8],
                                            "mirna_paired": f[9],
                                            "mirna_unpaired": f[10],
                                            "duplex_span": span})))
    return out

def run(con, mirna, tgts, opts=None, progress=None):
    """Fold this miRNA against every target transcript."""
    opts = opts or {}
    cutoff = float(opts.get("energy_cutoff", -15.0))
    per_target = int(opts.get("hits_per_target", 3))
    refseqs = [t["refseq"] for t in tgts]
    seqs = {r: s.replace("T", "U") for r, s in T.sequences(con, refseqs).items() if s}
    regs = T.regions(con, refseqs)
    by_refseq = {t["refseq"]: t for t in tgts if t["refseq"] in seqs}
    prov = {"tool": "rnahybrid", "version": META["version"], "params": {}}
    if not seqs:
        return {"records": [], "provenance": prov, "warnings": ["no sequences"]}
    maxlen = max(len(s) for s in seqs.values()) + 10
    prov["params"] = {"f": "2,7", "s": "3utr_human", "e": cutoff,
                      "b": per_target, "m": maxlen}
    work = tempfile.mkdtemp(prefix="rnahybrid_")
    try:
        tf, qf = os.path.join(work, "t.fa"), os.path.join(work, "q.fa")
        with open(tf, "w") as fh:
            for r, s in seqs.items():
                fh.write(">%s\n%s\n" % (r, _wrap(s)))
        with open(qf, "w") as fh:
            fh.write(">%s\n%s\n" % (mirna["name"], mirna["sequence"]))
        p = subprocess.run([BIN, "-t", tf, "-q", qf, "-s", "3utr_human",
                            "-f", "2,7", "-c", "-b", str(per_target),
                            "-e", str(cutoff), "-m", str(maxlen)],
                           capture_output=True, text=True)
        if p.returncode != 0 and not p.stdout.strip():
            raise RuntimeError("RNAhybrid failed: %s" % p.stderr.strip()[:300])
        out = _parse(p.stdout, mirna, by_refseq, seqs, regs)
        warn = [p.stderr.strip()[:300]] if p.stderr.strip() else []
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"records": out, "provenance": prov, "warnings": warn}
