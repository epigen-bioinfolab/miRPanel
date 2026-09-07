"""Turn any identifier a user types into our internal keys.

Loaders, the orchestrator and the API all resolve through this module, so
they can never disagree about what a name means.
"""

COLS = "accession, name, seed, species"
MCOLS = "m.accession, m.name, m.seed, m.species"

def _clean(text):
    """Trim and collapse internal whitespace."""
    return " ".join(str(text).split())

def _species_codes(con):
    """The prefixes miRBase actually uses, read from our own table."""
    return {s for (s,) in con.execute("SELECT DISTINCT species FROM mirnas")}

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

def resolve_mirna(con, text, species="hsa"):
    """Resolve a miRNA identifier to one record.

    Returns a dict with accession/name/seed/species plus matched_by, or
    matched_by="ambiguous" with candidates, or None if nothing matches.
    """
    key = _clean(text)
    if not key:
        return None
    tries = [key]
    if key.split("-")[0].lower() not in _species_codes(con):
        tries.append(species + "-" + key)
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
            a, n, s, sp = rows[0]
            return {"input": text, "matched_by": how, "accession": a,
                    "name": n, "seed": s, "species": sp}
    return None

GENE_STEPS = (
    ("symbol", "SELECT DISTINCT entrez, symbol FROM genes WHERE symbol=? COLLATE NOCASE", 0),
    ("ensembl gene", "SELECT DISTINCT entrez, symbol FROM genes WHERE ensembl_base=? COLLATE NOCASE", 1),
    ("refseq", "SELECT DISTINCT entrez, symbol FROM transcripts WHERE refseq_base=? COLLATE NOCASE", 1),
    ("ensembl tx", "SELECT DISTINCT entrez, symbol FROM transcripts WHERE ensembl_base=? COLLATE NOCASE", 1),
    ("gene alias", "SELECT DISTINCT g.entrez, g.symbol FROM gene_aliases a "
                   "JOIN genes g ON g.entrez=a.entrez WHERE a.alias=? COLLATE NOCASE", 0))

def resolve_gene(con, text):
    """Resolve a gene identifier: Entrez id, symbol, alias, Ensembl or RefSeq."""
    key = _clean(text)
    if not key:
        return None
    if key.isdigit():
        r = con.execute("SELECT entrez, symbol FROM genes WHERE entrez=?", (key,)).fetchone()
        if r:
            return {"input": text, "matched_by": "entrez", "entrez": r[0], "symbol": r[1]}
    base = key.split(".")[0]
    for how, sql, strip in GENE_STEPS:
        rows = con.execute(sql, (base if strip else key,)).fetchall()
        if len(rows) == 1:
            return {"input": text, "matched_by": how, "entrez": rows[0][0], "symbol": rows[0][1]}
        if len(rows) > 1:
            return {"input": text, "matched_by": "ambiguous",
                    "candidates": sorted({r[0] for r in rows})}
    return None
