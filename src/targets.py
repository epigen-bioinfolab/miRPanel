"""The transcripts a job examines, and their sequences and regions."""

def all_targets(con):
    """Every MANE Select transcript: entrez, refseq, symbol, length."""
    return [{"entrez": e, "refseq": r, "symbol": s, "length": n}
            for e, r, s, n in con.execute(
                "SELECT entrez, refseq, symbol, length FROM transcripts "
                "WHERE mane_status='MANE Select' ORDER BY entrez")]

def targets_for(con, entrez_ids):
    """The MANE Select transcripts for a specific set of genes."""
    want = set(entrez_ids)
    return [t for t in all_targets(con) if t["entrez"] in want]

def sequences(con, refseqs=None):
    """{refseq: sequence}; every transcript when refseqs is None."""
    if refseqs is None:
        return {r: s for r, s in con.execute(
            "SELECT refseq, sequence FROM transcripts")}
    want = set(refseqs)
    if len(want) <= 500:
        qs = ",".join("?" * len(want))
        return {r: s for r, s in con.execute(
            "SELECT refseq, sequence FROM transcripts WHERE refseq IN (%s)" % qs,
            tuple(want))}
    return {r: s for r, s in con.execute(
        "SELECT refseq, sequence FROM transcripts") if r in want}

def regions(con, refseqs=None):
    """{refseq: [(region, start, end)]}, 1-based inclusive."""
    want = None if refseqs is None else set(refseqs)
    out = {}
    for rs, reg, a, b in con.execute(
            "SELECT refseq, region, start_pos, end_pos FROM regions"):
        if want is None or rs in want:
            out.setdefault(rs, []).append((reg, a, b))
    return out

def region_of(regs, pos):
    """Which region a 1-based transcript position falls in."""
    for name, a, b in regs:
        if a <= pos <= b:
            return name
    return None
