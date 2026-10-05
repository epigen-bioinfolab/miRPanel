"""Store GO and KEGG enrichment: one row per analysis, many rows of output.

Nothing here is ever deleted. Re-running a job does not touch the enrichment
that came before it; each run keeps the gene ids it actually tested and the
job's finished_at at the time, so an old scientific result stays readable and
the interface can tell a current run from a historical one by comparing the
two timestamps.

Every p-value is stored with the four integers of its hypergeometric test:

    k  of your genes are in the term
    n  of your genes the annotation could place in this ontology at all
    K  of the background are in the term
    N  of the background the annotation could place in this ontology

n is NOT the size of your gene list and N is NOT the size of your background.
org.Hs.eg.db annotates a different subset for each ontology, and KEGG knows
roughly half the genome. Measured on 381 conserved miR-21 targets: n was 357
for GO:BP, 372 for GO:CC, 362 for GO:MF and 190 for KEGG; N was 17116, 18206,
17807 and 8516. Storing one pair per run would have made every p-value in the
database unrecomputable. So they are stored per term, which means anyone can
redo the arithmetic in any language, forever, without R.
"""
import datetime
import hashlib
import json
import os
import subprocess

import species as sp
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agreement
import geneset

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RSCRIPT = os.path.join(HERE, "R", "enrich.R")
TMP = os.path.join(HERE, "data", "tmp")

# Fixed in R/enrich.R. Recorded on every run so a result read next year states
# the test it came from instead of the test we happen to run then.
P_ADJUST_METHOD = "BH"
P_CUTOFF = 0.05
Q_CUTOFF = 0.2
ONTOLOGIES = "GO:BP,GO:CC,GO:MF,KEGG"

COLS = ("source", "term_id", "description", "gene_ratio", "bg_ratio",
        "p_value", "p_adjust", "q_value", "n_genes", "genes")

SPEC_KEYS = ("seed", "targetscan", "rnahybrid", "mirtarbase", "regions", "match",
            # An explicit gene list - a click on one exclusive region of the
            # agreement diagram - plus the tool names that produced it, kept
            # only so the stored sentence can name them (see create()).
            "genes", "in", "out")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def normalise(spec):
    """One question, one spelling.

    'all regions' and 'no region filter' are the same question; so are
    match='all' and no match at all. Collapsing them here means the same
    filter always produces the same hash, so a repeat request finds the run
    that already exists instead of computing it again.
    """
    out = {}
    for k in SPEC_KEYS:
        v = spec.get(k)
        if v in (None, "", [], "none"):
            continue
        if k == "regions":
            v = sorted(v)
            if v == sorted(geneset.REGIONS):
                continue
        elif k == "match":
            v = str(v).lower()
            if v == "all":
                continue
        elif k == "genes":
            v = sorted(set(int(g) for g in v))
        elif k in ("in", "out"):
            v = sorted(str(x) for x in v)
        else:
            v = str(v)
        out[k] = v
    return out


def spec_hash(spec):
    return hashlib.sha1(
        json.dumps(normalise(spec), sort_keys=True).encode()).hexdigest()[:12]


def background(con, species=None):
    """The genes that could have been selected, and which release they are.

    Refuses to guess. An enrichment whose background cannot be traced to a
    named release is not reproducible, and a p-value that cannot be traced is
    not worth storing.

    Returns (id, symbol) pairs rather than bare ids, because the stored id
    is an Ensembl one for every organism except human, and R has to try
    more than one key to map it.
    """
    species = species or sp.DEFAULT
    rows = con.execute(
        "SELECT DISTINCT t.entrez, t.symbol FROM transcripts t "
        "WHERE t.canonical=1 AND t.species=?", (species,)).fetchall()
    if not rows:
        raise RuntimeError("no canonical transcripts loaded for %s" % species)

    row = con.execute(
        "SELECT name, version FROM data_sources WHERE name=?",
        (sp.source_name(species),)).fetchone()
    if not row:
        raise RuntimeError("no data_sources row for %s: refusing to run an "
                           "enrichment whose background has no release"
                           % species)
    return rows, row[0], row[1]


def _read_meta(path):
    return dict(l.split("\t", 1)
                for l in open(path).read().splitlines() if "\t" in l)


def _int(meta, key):
    v = meta.get(key)
    return int(v) if v not in (None, "") else None


def _read_terms(path, run_id):
    """Parse enrich.R's table into rows, checking it as we go.

    Two integrity checks that would otherwise fail silently: the column names
    must be the ones this code was written against, and each term's gene list
    must hold exactly k symbols. Both raise rather than store something wrong.
    """
    lines = open(path).read().splitlines()
    if not lines:
        raise RuntimeError("enrich.R wrote an empty file: %s" % path)
    head = lines[0].split("\t")
    if head != list(COLS):
        raise RuntimeError("enrich.R changed its columns.\n  expected %s\n  got      %s"
                           % (list(COLS), head))
    rows = []
    for ln in lines[1:]:
        f = ln.split("\t")
        if len(f) != len(COLS):
            raise RuntimeError("malformed row: %d fields, expected %d: %.90s"
                               % (len(f), len(COLS), ln))
        r = dict(zip(COLS, f))
        k, n = (int(x) for x in r["gene_ratio"].split("/"))
        K, N = (int(x) for x in r["bg_ratio"].split("/"))
        genes = r["genes"]
        if len(genes.split("/")) != k:
            raise RuntimeError("%s says %d genes but lists %d"
                               % (r["term_id"], k, len(genes.split("/"))))
        rows.append((run_id, r["source"], r["term_id"], r["description"],
                     k, n, K, N,
                     float(r["p_value"]), float(r["p_adjust"]),
                     float(r["q_value"]) if r["q_value"] else None, genes))
    return rows


def create(con, job_id, spec):
    """Register one enrichment and queue it. Returns the run_id.

    Everything cheap and everything that can be wrong happens here - resolving
    the gene list, finding the background release, checking the job exists - so
    a bad request fails immediately instead of two minutes later inside a
    worker. The gene list is stored now, not recomputed later, so the run tests
    exactly the set that existed when it was asked for.
    """
    spec = normalise(spec)
    sel = geneset.select(con, job_id, spec)
    if not sel["count"]:
        raise ValueError("no genes selected - nothing to test")

    if spec.get("genes") is not None:
        # A gene list with no rule of its own - the agreement diagram's own
        # words for the region name the genes, sharing agreement.py's
        # wording so a run started from a click describes itself the same
        # way the click did.
        label = agreement.region_label(spec.get("in") or [], spec.get("out") or [])
        sel["sentence"] = "%d gene%s found %s" % (
            sel["count"], "" if sel["count"] == 1 else "s", label)

    finished = con.execute("SELECT finished_at, params FROM jobs "
                           "WHERE job_id=?", [job_id]).fetchone()
    if finished is None:
        raise ValueError("no such job: %s" % job_id)

    # The background belongs to the organism the job ran on. Asking for
    # the human one regardless meant a rabbit run was stored as having
    # tested 19,363 human genes against MANE v1.5.
    import orchestrator
    species = orchestrator.job_species(json.loads(finished[1]))
    bg, bg_source, bg_version = background(con, species)

    run_id = "enr_" + uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO enrichment_runs (run_id, job_id, job_finished_at, "
        "created_at, status, spec_json, spec_hash, rule_sentence, "
        "gene_ids, n_genes, background, background_source, background_version, "
        "n_background, p_adjust_method, p_cutoff, q_cutoff, ontologies) "
        "VALUES (?,?,?,?,'queued',?,?,?,?,?,'mane_select',?,?,?,?,?,?,?)",
        [run_id, job_id, finished[0], _now(),
         json.dumps(spec, sort_keys=True), spec_hash(spec), sel["sentence"],
         ",".join(str(g) for g in sel["genes"]), sel["count"],
         bg_source, bg_version, len(bg),
         P_ADJUST_METHOD, P_CUTOFF, Q_CUTOFF, ONTOLOGIES])
    con.commit()
    return run_id


def execute(con, run_id):
    """Run R for one enrichment and store what comes back.

    The slow half. Reads the gene list the request already fixed, so this can
    run minutes or hours later and still test the same genes.
    """
    row = con.execute("SELECT gene_ids, n_genes, job_id FROM enrichment_runs "
                      "WHERE run_id=?", [run_id]).fetchone()
    if row is None:
        raise ValueError("no such enrichment run: %s" % run_id)
    genes = row[0].split(",")
    n_selected = row[1]

    import orchestrator
    jp = con.execute("SELECT params FROM jobs WHERE job_id=?",
                     (row[2],)).fetchone()
    species = orchestrator.job_species(json.loads(jp[0])) if jp else sp.DEFAULT
    # An uploaded organism carries its scientific name on the upload
    # rather than in the registry, and that name is what AnnotationHub
    # is searched by.
    latin = None
    if sp.is_upload(species):
        import uploads
        up = uploads.get(con, species[len(sp.UPLOAD_PREFIX):])
        latin = up and up.get("latin")
    rec = sp.get(species, latin=latin)
    if not rec["orgdb"] and not rec["latin"]:
        raise RuntimeError("GO and KEGG need an annotation database, and "
                           "none can be found without a scientific name "
                           "for this organism. Re-upload it giving the "
                           "species name, for example Xenopus tropicalis.")

    bg = background(con, species)[0]
    # Symbols travel alongside the ids: R picks whichever key maps best
    # for this organism, which is the Ensembl id for mouse and the alias
    # for rabbit.
    sym = dict(con.execute(
        "SELECT entrez, symbol FROM genes WHERE species=?", (species,)))
    con.execute("UPDATE enrichment_runs SET status='running', started_at=? "
                "WHERE run_id=?", [_now(), run_id])
    con.commit()

    os.makedirs(TMP, exist_ok=True)
    gp = os.path.join(TMP, "%s_genes.txt" % run_id)
    bp = os.path.join(TMP, "%s_background.txt" % run_id)
    op = os.path.join(TMP, "%s.tsv" % run_id)
    mp = os.path.join(TMP, "%s_meta.tsv" % run_id)
    open(gp, "w").write("".join(
        "%s\t%s\n" % (g, sym.get(g, "")) for g in genes))
    open(bp, "w").write("".join(
        "%s\t%s\n" % (g, s or "") for g, s in bg))

    t0 = time.time()
    try:
        p = subprocess.run(["Rscript", RSCRIPT, gp, bp, op, mp,
                            rec["orgdb"] or "", rec["latin"] or "",
                            rec["kegg"] or ""],
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError("Rscript failed (%d): %s"
                               % (p.returncode, p.stderr.strip()[-500:]))
        meta = _read_meta(mp)
        # How the ids were mapped and how much of the background made it.
        # Human is always 100% through Entrez; rabbit is nearer two thirds
        # through aliases, and that has to be visible in the result.
        con.execute(
            "UPDATE enrichment_runs SET id_key=?, mapped_fraction=? "
            "WHERE run_id=?",
            (meta.get("id_key"), meta.get("mapped_fraction"), run_id))
        # R reads the file itself and de-duplicates. n_input is what it was
        # handed; n_genes is what survived mapping to Entrez, which is lower
        # for organisms whose annotation is incomplete. The first must match
        # what we selected, or the stored gene_ids are not the list that
        # produced these p-values. The second is reported, not enforced.
        if _int(meta, "n_input") != n_selected:
            raise RuntimeError("R was given %s genes but %d were selected"
                               % (meta.get("n_input"), n_selected))
        terms = _read_terms(op, run_id)
        con.executemany(
            "INSERT OR REPLACE INTO enrichment_terms (run_id, source, term_id, "
            "description, k_in_term_and_list, n_in_list, k_in_term_and_background, "
            "n_in_background, p_value, p_adjust, q_value, genes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", terms)
        con.execute(
            "UPDATE enrichment_runs SET status='done', finished_at=?, seconds=?, "
            "n_genes_annotated=?, n_background_annotated=?, r_version=?, "
            "clusterprofiler_version=?, orgdb_version=?, kegg_ok=?, "
            "kegg_fetched_at=?, n_terms=? WHERE run_id=?",
            [_now(), round(time.time() - t0, 1),
             _int(meta, "n_genes_annotated"), _int(meta, "n_background_annotated"),
             meta.get("r_version"), meta.get("clusterprofiler_version"),
             meta.get("orgdb_version"), _int(meta, "kegg_ok"),
             meta.get("kegg_fetched_at"), len(terms), run_id])
        con.commit()
    except Exception as e:
        con.execute("UPDATE enrichment_runs SET status='failed', finished_at=?, "
                    "seconds=?, error=? WHERE run_id=?",
                    [_now(), round(time.time() - t0, 1), str(e)[:1000], run_id])
        con.commit()
        raise
    return run_id


def run(con, job_id, spec):
    """Queue and run in one go. For the command line and the tests; the API
    queues and lets the worker do the second half."""
    return execute(con, create(con, job_id, spec))


def next_queued(con):
    """Atomically claim the oldest queued enrichment. Returns run_id or None."""
    row = con.execute("SELECT run_id FROM enrichment_runs WHERE status='queued' "
                      "ORDER BY created_at LIMIT 1").fetchone()
    if row is None:
        return None
    cur = con.execute("UPDATE enrichment_runs SET status='running', started_at=? "
                      "WHERE run_id=? AND status='queued'", [_now(), row[0]])
    con.commit()
    return row[0] if cur.rowcount else None


def requeue_stale(con):
    """Put enrichments left 'running' by a crashed worker back in the queue."""
    cur = con.execute("UPDATE enrichment_runs SET status='queued', started_at=NULL "
                      "WHERE status='running'")
    con.commit()
    return cur.rowcount


# ---------------------------------------------------------------- reading

def _dicts(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_run(con, run_id):
    rows = _dicts(con.execute("SELECT * FROM enrichment_runs WHERE run_id=?",
                              [run_id]))
    if not rows:
        return None
    r = rows[0]
    r["genes"] = r.pop("gene_ids").split(",")
    job = con.execute("SELECT finished_at FROM jobs WHERE job_id=?",
                      [r["job_id"]]).fetchone()
    # the job may have been re-run since; say so rather than hiding it
    r["stale"] = bool(job and job[0] != r["job_finished_at"])
    return r


def list_runs(con, job_id):
    return _dicts(con.execute(
        "SELECT run_id, created_at, status, rule_sentence, n_genes, n_terms, "
        "spec_hash FROM enrichment_runs WHERE job_id=? ORDER BY created_at DESC",
        [job_id]))


def find(con, job_id, spec):
    """The most recent completed run of exactly this filter, if there is one."""
    rows = _dicts(con.execute(
        "SELECT run_id FROM enrichment_runs WHERE job_id=? AND spec_hash=? "
        "AND status='done' ORDER BY created_at DESC LIMIT 1",
        [job_id, spec_hash(spec)]))
    return rows[0]["run_id"] if rows else None


def _term_where(run_id, source, q):
    """Shared by the count and the page, so the two can never disagree."""
    where, args = ["run_id=?"], [run_id]
    if source:
        where.append("source=?")
        args.append(source)
    if q:
        # % and _ are wildcards in LIKE. Someone typing them means the
        # characters, so they are escaped rather than honoured.
        pat = "%" + q.replace("\\", "\\\\").replace("%", "\\%") \
                     .replace("_", "\\_") + "%"
        # genes are stored slash-separated, so a plain substring match is
        # what a search box should do: typing PTEN finds every term PTEN
        # drives, and typing PT finds it while you are still typing. It will
        # also match PTENP1 - that is a search, not a lookup.
        where.append("(description LIKE ? ESCAPE '\\' "
                     "OR term_id LIKE ? ESCAPE '\\' "
                     "OR genes LIKE ? ESCAPE '\\')")
        args += [pat, pat, pat]
    return " AND ".join(where), args


def count_terms(con, run_id, source=None, q=None):
    where, args = _term_where(run_id, source, q)
    return con.execute("SELECT COUNT(*) FROM enrichment_terms WHERE " + where,
                       args).fetchone()[0]


def terms(con, run_id, source=None, limit=None, offset=0, q=None):
    """One page of terms, always ordered by adjusted p.

    Searching narrows the set; it never reorders it, so a search cannot make a
    weaker term appear above a stronger one.
    """
    where, args = _term_where(run_id, source, q)
    sql = "SELECT * FROM enrichment_terms WHERE " + where + \
          " ORDER BY p_adjust, p_value"
    if limit:
        sql += " LIMIT ? OFFSET ?"
        args += [int(limit), int(offset)]
    return _dicts(con.execute(sql, args))
