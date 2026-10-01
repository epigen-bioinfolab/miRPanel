"""The transcripts a job examines, and their sequences and regions.

EVERY function here is scoped to ONE species. That is not optional
decoration: `transcripts` now holds more than one organism, so a query
without a species filter silently returns a mixture. A transcriptome-
wide human job would scan mouse transcripts and report the hits as
human results - wrong, and wrong in a way that still looks plausible.

`species` defaults to human so that every existing caller keeps its
current behaviour unchanged. Human results must come out byte-identical
to the pre-multi-species tool; that is the regression test for this
whole change.

The canonical transcript is now flagged by `canonical=1` rather than
`mane_status='MANE Select'`. For human the two are the same rows (the
column was backfilled from mane_status). For an Ensembl species there
is no MANE, so the flag carries "Ensembl canonical" instead - one
transcript per gene either way, which is the property every count in
this tool depends on.
"""

import species as sp

#: One transcript per gene, for one organism. Bind (species,).
CANONICAL = "canonical=1 AND species=?"


def all_targets(con, species=sp.DEFAULT):
    """Every canonical transcript: entrez, refseq, symbol, length."""
    sp.get(species)                      # fail loudly on a typo'd key
    return [{"entrez": e, "refseq": r, "symbol": s, "length": n}
            for e, r, s, n in con.execute(
                "SELECT entrez, refseq, symbol, length FROM transcripts "
                "WHERE " + CANONICAL + " ORDER BY entrez", (species,))]


def targets_for(con, entrez_ids, species=sp.DEFAULT):
    """The canonical transcripts for a specific set of genes."""
    want = set(entrez_ids)
    return [t for t in all_targets(con, species) if t["entrez"] in want]


def sequences(con, refseqs=None, species=sp.DEFAULT):
    """{refseq: sequence}.

    With refseqs=None this returns every canonical transcript OF ONE
    SPECIES. It previously returned the whole table, which was the
    same thing when only human was loaded and is not any more.

    When refseqs is given, no species filter is applied: refseq is the
    primary key, so the ids already name exactly which rows are
    wanted, whatever organism they came from.
    """
    if refseqs is None:
        sp.get(species)
        return {r: s for r, s in con.execute(
            "SELECT refseq, sequence FROM transcripts WHERE " + CANONICAL,
            (species,))}
    want = set(refseqs)
    if len(want) <= 500:
        qs = ",".join("?" * len(want))
        return {r: s for r, s in con.execute(
            "SELECT refseq, sequence FROM transcripts WHERE refseq IN (%s)"
            % qs, tuple(want))}
    return {r: s for r, s in con.execute(
        "SELECT refseq, sequence FROM transcripts") if r in want}


def regions(con, refseqs=None, species=sp.DEFAULT):
    """{refseq: [(region, start, end)]}, 1-based inclusive.

    `regions` has no species column of its own - it keys on refseq,
    which belongs to exactly one transcript and therefore to exactly
    one species. So scoping happens through a join rather than a
    column, and no schema change was needed.
    """
    if refseqs is None:
        sp.get(species)
        out = {}
        for rs, reg, a, b in con.execute(
                "SELECT r.refseq, r.region, r.start_pos, r.end_pos "
                "FROM regions r JOIN transcripts t ON t.refseq = r.refseq "
                "WHERE t.canonical=1 AND t.species=?", (species,)):
            out.setdefault(rs, []).append((reg, a, b))
        return out

    want = set(refseqs)
    out = {}
    for rs, reg, a, b in con.execute(
            "SELECT refseq, region, start_pos, end_pos FROM regions"):
        if rs in want:
            out.setdefault(rs, []).append((reg, a, b))
    return out


def region_of(regs, pos):
    """Which region a 1-based transcript position falls in."""
    for name, a, b in regs:
        if a <= pos <= b:
            return name
    return None


def counts(con):
    """{species: n} over canonical transcripts - for /about and sanity."""
    return {s: n for s, n in con.execute(
        "SELECT species, COUNT(*) FROM transcripts WHERE canonical=1 "
        "GROUP BY species ORDER BY species")}
