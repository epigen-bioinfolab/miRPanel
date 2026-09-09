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
                          low_confidence=(mfe > -25.0),
                          extra=json.dumps({"target_unpaired": f[7],
                                            "target_paired": f[8],
                                            "mirna_paired": f[9],
                                            "mirna_unpaired": f[10],
                                            "duplex_span": span})))
    return out

def _deal(seqs, n):
    """Split the targets into n groups of roughly equal total length, longest
    first, so no worker is left folding a 100 kb transcript alone."""
    groups = [[] for _ in range(n)]
    load = [0] * n
    for r in sorted(seqs, key=lambda r: -len(seqs[r])):
        i = load.index(min(load))
        groups[i].append(r)
        load[i] += len(seqs[r])
    return [g for g in groups if g]


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
    # One RNAhybrid process is single-threaded, so the targets are dealt across
    # several processes. Every process gets identical parameters (including the
    # global -m), and folding one transcript never depends on another, so the
    # combined output is the same as one process would have produced.
    workers = int(opts.get("workers") or os.cpu_count() or 1)
    workers = max(1, min(workers, len(seqs)))
    prov["params"]["workers"] = workers

    work = tempfile.mkdtemp(prefix="rnahybrid_")
    try:
        qf = os.path.join(work, "q.fa")
        with open(qf, "w") as fh:
            fh.write(">%s\n%s\n" % (mirna["name"], mirna["sequence"]))

        procs = []
        for i, group in enumerate(_deal(seqs, workers)):
            tf = os.path.join(work, "t%d.fa" % i)
            with open(tf, "w") as fh:
                for r in group:
                    fh.write(">%s\n%s\n" % (r, _wrap(seqs[r])))
            # Each worker writes to its own file, never to a pipe. A pipe
            # holds only ~64 kB: once full, RNAhybrid blocks until someone
            # reads it, so eleven workers sat frozen while we drained the
            # first one. That made "parallel" runs almost serial.
            op = os.path.join(work, "out%d.txt" % i)
            ep = os.path.join(work, "err%d.txt" % i)
            oh, eh = open(op, "w"), open(ep, "w")
            procs.append((subprocess.Popen(
                [BIN, "-t", tf, "-q", qf, "-s", "3utr_human", "-f", "2,7",
                 "-c", "-b", str(per_target), "-e", str(cutoff),
                 "-m", str(maxlen)], stdout=oh, stderr=eh), oh, eh, op, ep))

        stdout, warn = [], []
        for proc, oh, eh, op, ep in procs:
            proc.wait()
            oh.close()
            eh.close()
            with open(op) as fh:
                o = fh.read()
            with open(ep) as fh:
                e = fh.read()
            if proc.returncode != 0 and not o.strip():
                raise RuntimeError("RNAhybrid failed: %s" % e.strip()[:300])
            stdout.append(o)
            if e.strip():
                warn.append(e.strip()[:300])
        out = _parse("".join(stdout), mirna, by_refseq, seqs, regs)
        warn = sorted(set(warn))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"records": out, "provenance": prov, "warnings": warn}
