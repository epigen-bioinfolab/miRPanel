"""Turn any identifier a user types into our internal keys.

Loaders, the orchestrator and the API all resolve through this module, so
they can never disagree about what a name means.

SPECIES SCOPING
---------------
Gene lookup is now scoped to one organism, and it has to be. Symbols
collide across species by design - human PTEN and mouse Pten are the
same name under COLLATE NOCASE - so an unscoped lookup returns two
rows and reports "ambiguous" for virtually every gene that has a mouse
ortholog. The scoping is what makes gene search work at all once a
second species is loaded, not a refinement.

`species` is the registry key ("human", "mouse", ...) and defaults to
human, so existing callers behave exactly as before.

miRNA lookup is scoped differently, through miRBase's own three-letter
prefix, which the names already carry. resolve_mirna accepts either
form - "mouse" or "mmu" - so callers that already pass a miRBase code
keep working untouched.
"""

import hashlib

import species as sp

COLS = "accession, name, seed, species, sequence"
MCOLS = "m.accession, m.name, m.seed, m.species, m.sequence"

#: A mature miRNA typed as bare sequence rather than as a name. Needed
#: because an organism the user uploads may not be in miRBase at all,
#: and then there is no name to look up - the sequence is the only
#: identifier that exists.
RAW_BASES = set("ACGUT")
RAW_MIN, RAW_MAX = 16, 30


def _looks_like_sequence(key):
    """Is this a bare nucleotide sequence rather than a name?

    No miRNA name or MIMAT accession is 16+ characters drawn only from
    ACGUT, so the test cannot swallow an identifier by accident.
    """
    k = "".join(key.split()).upper()
    return RAW_MIN <= len(k) <= RAW_MAX and set(k) <= RAW_BASES


def _synthetic(text, rna, species):
    """A record for a sequence miRBase does not have.

    The accession is derived from the sequence itself, so the same
    sequence always gets the same id and two jobs on it are comparable.
    The name IS the sequence: this miRNA has no other name, and writing
    one in would invent information. Seed is positions 2-8 as DNA,
    matching how miRBase rows are stored here (sequence in RNA, seed in
    DNA) - a mismatch there would make every seed search quietly find
    nothing.
    """
    dna = rna.replace("U", "T")
    return {"input": text,
            "matched_by": "raw sequence (not in miRBase)",
            "accession": "SEQ:" + hashlib.sha1(dna.encode()).hexdigest()[:12],
            "name": rna,
            "seed": dna[1:8],
            "species": species,
            "sequence": rna}


def resolve_sequence(con, text, species=sp.DEFAULT):
    """Resolve a bare mature sequence, or None if it is not one.

    miRBase is consulted first: someone who pastes let-7a's sequence
    should get let-7a, with its real accession and its real name, not an
    anonymous record. Only a sequence genuinely absent from miRBase gets
    a synthetic one.
    """
    rna = "".join(text.split()).upper().replace("T", "U")
    if not _looks_like_sequence(text):
        return None
    rows = con.execute("SELECT " + COLS + " FROM mirnas WHERE sequence=?",
                       (rna,)).fetchall()
    if rows:
        code = _mirbase_code(species)
        # Conserved miRNAs are sequence-identical across organisms, so
        # one sequence can match many rows. Prefer this job's species;
        # otherwise take the first and say which it was.
        same = [r for r in rows if r[3] == code]
        a, n, s, spc, q = (same or rows)[0]
        return {"input": text,
                "matched_by": "sequence" if same
                              else "sequence (%s record)" % spc,
                "accession": a, "name": n, "seed": s,
                "species": spc, "sequence": q}
    return _synthetic(text, rna, _mirbase_code(species))


def _clean(text):
    """Trim and collapse internal whitespace."""
    return " ".join(str(text).split())


def _species_codes(con):
    """The prefixes miRBase actually uses, read from our own table."""
    return {s for (s,) in con.execute("SELECT DISTINCT species FROM mirnas")}


def _mirbase_code(species):
    """Accept a registry key ('mouse') or a miRBase code ('mmu')."""
    rec = sp.SPECIES.get(species)
    return rec["mirbase"] if rec else species


def _by_acc(con, k):
    return con.execute("SELECT " + COLS + " FROM mirnas WHERE accession=?", (k,)).fetchall()


def _by_name(con, k):
    return con.execute("SELECT " + COLS + " FROM mirnas WHERE name=?", (k,)).fetchall()


def _by_name_ci(con, k):
    return con.execute("SELECT " + COLS + " FROM mirnas WHERE name=? COLLATE NOCASE", (k,)).fetchall()


def _by_alias(con, k):
    return con.execute("SELECT DISTINCT " + MCOLS + " FROM mirna_aliases a "
                       "JOIN mirnas m ON m.accession=a.accession WHERE a.alias=?", (k,)).fetchall()


def _by_alias_ci(con, k):
    return con.execute("SELECT DISTINCT " + MCOLS + " FROM mirna_aliases a "
                       "JOIN mirnas m ON m.accession=a.accession WHERE a.alias=? COLLATE NOCASE",
                       (k,)).fetchall()


def resolve_mirna(con, text, species=sp.DEFAULT):
    """Resolve a miRNA identifier to one record.

    Returns a dict with accession/name/seed/species plus matched_by, or
    matched_by="ambiguous" with candidates, or None if nothing matches.

    A bare name ("miR-21-5p") is retried with the species prefix
    attached, so the same box works whichever organism is selected.
    A fully-qualified name from another organism ("hsa-miR-21-5p" on a
    mouse run) still resolves here - it is a real miRNA - and the
    orchestrator decides whether to allow the cross-species query.
    """
    key = _clean(text)
    if not key:
        return None
    # Checked before the name steps: a bare sequence can never be a
    # name, so this cannot shadow a real identifier, and for an uploaded
    # organism it is the only input that works at all.
    if _looks_like_sequence(key):
        return resolve_sequence(con, key, species)
    code = _mirbase_code(species)
    tries = [key]
    if key.split("-")[0].lower() not in _species_codes(con):
        tries.append(code + "-" + key)
    steps = (("accession", _by_acc), ("name", _by_name), ("alias", _by_alias),
             ("name/case", _by_name_ci), ("alias/case", _by_alias_ci))
    for k in tries:
        for how, fn in steps:
            rows = fn(con, k)
            if not rows:
                continue
            if len(rows) > 1:
                return {"input": text, "matched_by": "ambiguous",
                        "candidates": sorted(r[0] for r in rows)}
            a, n, s, spc, q = rows[0]
            return {"input": text, "matched_by": how, "accession": a,
                    "name": n, "seed": s, "species": spc, "sequence": q}
    return None


# Each step binds (key, species). `strip` means try the versionless
# base of the identifier (ENSMUST00000100497.11 -> ENSMUST00000100497).
GENE_STEPS = (
    ("symbol",
     "SELECT DISTINCT entrez, symbol FROM genes "
     "WHERE symbol=? COLLATE NOCASE AND species=?", 0),
    ("ensembl gene",
     "SELECT DISTINCT entrez, symbol FROM genes "
     "WHERE ensembl_base=? COLLATE NOCASE AND species=?", 1),
    ("refseq",
     "SELECT DISTINCT entrez, symbol FROM transcripts "
     "WHERE refseq_base=? COLLATE NOCASE AND species=?", 1),
    ("ensembl tx",
     "SELECT DISTINCT entrez, symbol FROM transcripts "
     "WHERE ensembl_base=? COLLATE NOCASE AND species=?", 1),
    ("gene alias",
     "SELECT DISTINCT g.entrez, g.symbol FROM gene_aliases a "
     "JOIN genes g ON g.entrez=a.entrez "
     "WHERE a.alias=? COLLATE NOCASE AND g.species=?", 0))


def resolve_gene(con, text, species=sp.DEFAULT):
    """Resolve a gene identifier: Entrez id, symbol, alias, Ensembl or RefSeq.

    Scoped to one organism. For non-human species the `entrez` column
    holds the Ensembl gene id rather than a real Entrez id (Ensembl
    files carry no Entrez mapping), so `key.isdigit()` simply never
    fires there and the symbol/Ensembl steps do the work.
    """
    key = _clean(text)
    if not key:
        return None
    sp.get(species)
    if key.isdigit():
        r = con.execute("SELECT entrez, symbol FROM genes "
                        "WHERE entrez=? AND species=?",
                        (key, species)).fetchone()
        if r:
            return {"input": text, "matched_by": "entrez",
                    "entrez": r[0], "symbol": r[1]}
    base = key.split(".")[0]
    for how, sql, strip in GENE_STEPS:
        rows = con.execute(sql, (base if strip else key, species)).fetchall()
        if len(rows) == 1:
            return {"input": text, "matched_by": how,
                    "entrez": rows[0][0], "symbol": rows[0][1]}
        if len(rows) > 1:
            return {"input": text, "matched_by": "ambiguous",
                    "candidates": sorted({r[0] for r in rows})}
    return None
