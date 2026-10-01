"""Organisms a user supplied themselves.

miRPanel ships five organisms, chosen from a dropdown. This is for a
sixth: somebody working on Xenopus, or C. elegans, or anything else
nobody loaded, who brings the transcript sequences and the annotation
and gets the same analysis.

HOW IT FITS THE REST OF THE TOOL
--------------------------------
An upload is stored under the species key "upload:<id>", in the same
`transcripts`, `regions` and `genes` tables as every shipped organism.
Nothing downstream needed changing: species.get() answers for upload
keys, and no part of this codebase hardcodes the five.

WHAT AN UPLOADED ORGANISM CAN RUN
---------------------------------
Seed analysis and RNAhybrid, and that is permanent rather than pending.
scanMiR needs a species-specific KdModel collection built from the
McGeary CNN; TargetScan and miRTarBase are published per-species
datasets. None can exist for an organism nobody built them for. The two
that remain compute from sequence alone and work on anything.

The miRNA is the other half of that problem: an organism outside
miRBase has no miRNA names either, which is why resolve.py accepts a
bare mature sequence.

WHY UPLOADS ARE DELETED AND OTHER THINGS ARE NOT
------------------------------------------------
Enrichment runs and reports are never deleted - they are dated
scientific artefacts. An upload is not: it is a copy of files the user
already has on their own disk, kept only long enough to answer their
questions. Holding it forever would accumulate gigabytes of other
people's genomes for no benefit anyone asked for.

The sweep measures IDLE time, not age. last_used_at is touched whenever
a job reads the upload, so somebody reading their results for three
hours does not have the data pulled out from under them mid-session.
"""
import hashlib
import os
import shutil
import time
import uuid
from datetime import datetime, timedelta

import species as sp

UPLOAD_DIR = "data/uploads"

#: Hours of no use after which an upload and its files are removed.
SWEEP_HOURS = 24

#: A GTF with no canonical transcripts at all is not an Ensembl GTF, or
#: is a fragment. Parsing it produces nothing and the user should be
#: told why rather than handed an empty result.
MIN_TRANSCRIPTS = 50

#: Proportion of transcripts whose GTF exon lengths may disagree with
#: the FASTA before the pair is rejected. A handful can differ for
#: legitimate reasons; a large fraction means the two files are from
#: different releases, and every coordinate downstream would be wrong.
MAX_MISMATCH_FRACTION = 0.02


def now():
    return datetime.now().isoformat(timespec="seconds")


def _loader():
    """scripts/load_ensembl.py, imported by path.

    The parser lives in the script because that is where it was built
    and verified against all five shipped organisms. Importing it rather
    than reimplementing it means an upload is parsed by exactly the same
    code, with exactly the same checks, as a shipped species.
    """
    import importlib.util
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "scripts", "load_ensembl.py")
    spec = importlib.util.spec_from_file_location("_load_ensembl", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def species_key(upload_id):
    return sp.UPLOAD_PREFIX + upload_id


def create_streamed(con, label, fasta_name, fasta_fh, gtf_name, gtf_fh):
    """Like create(), but copies from open file objects.

    A cDNA FASTA can be well over a hundred megabytes. Reading one into
    memory to hand it over as bytes would hold the whole thing in RAM
    for no reason, and two at once on a shared server is worse. The
    HTTP layer uses this; create() stays for scripts and tests, where
    the files are small or already in hand.
    """
    label = " ".join(str(label or "").split()) or "Uploaded organism"
    upload_id = "up_" + uuid.uuid4().hex[:12]
    folder = os.path.join(UPLOAD_DIR, upload_id)
    os.makedirs(folder, exist_ok=True)

    paths = []
    for name, fh in ((fasta_name, fasta_fh), (gtf_name, gtf_fh)):
        path = os.path.join(folder, os.path.basename(name))
        with open(path, "wb") as out:
            shutil.copyfileobj(fh, out, 1 << 20)
        paths.append(path)
    fasta_path, gtf_path = paths

    con.execute(
        "INSERT INTO uploads (upload_id, label, created_at, last_used_at, "
        "status, fasta_name, gtf_name, fasta_path, gtf_path, fasta_sha256, "
        "gtf_sha256, bytes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (upload_id, label, now(), now(), "queued",
         os.path.basename(fasta_name), os.path.basename(gtf_name),
         fasta_path, gtf_path, _sha256(fasta_path), _sha256(gtf_path),
         os.path.getsize(fasta_path) + os.path.getsize(gtf_path)))
    con.commit()
    return upload_id


def create(con, label, fasta_name, fasta_bytes, gtf_name, gtf_bytes):
    """Store both files and queue the parse. Returns the upload id.

    Parsing a vertebrate transcriptome takes tens of seconds, so this
    queues like every other slow thing in the tool rather than holding
    an HTTP request open.
    """
    label = " ".join(str(label or "").split()) or "Uploaded organism"
    upload_id = "up_" + uuid.uuid4().hex[:12]
    folder = os.path.join(UPLOAD_DIR, upload_id)
    os.makedirs(folder, exist_ok=True)

    fasta_path = os.path.join(folder, os.path.basename(fasta_name))
    gtf_path = os.path.join(folder, os.path.basename(gtf_name))
    with open(fasta_path, "wb") as fh:
        fh.write(fasta_bytes)
    with open(gtf_path, "wb") as fh:
        fh.write(gtf_bytes)

    con.execute(
        "INSERT INTO uploads (upload_id, label, created_at, last_used_at, "
        "status, fasta_name, gtf_name, fasta_path, gtf_path, fasta_sha256, "
        "gtf_sha256, bytes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (upload_id, label, now(), now(), "queued",
         os.path.basename(fasta_name), os.path.basename(gtf_name),
         fasta_path, gtf_path, _sha256(fasta_path), _sha256(gtf_path),
         len(fasta_bytes) + len(gtf_bytes)))
    con.commit()
    return upload_id


def get(con, upload_id):
    row = con.execute(
        "SELECT upload_id, label, created_at, started_at, finished_at, "
        "last_used_at, status, error, fasta_name, gtf_name, bytes, "
        "n_transcripts, n_regions, n_skipped, seconds "
        "FROM uploads WHERE upload_id=?", (upload_id,)).fetchone()
    if row is None:
        return None
    cols = ("upload_id", "label", "created_at", "started_at", "finished_at",
            "last_used_at", "status", "error", "fasta_name", "gtf_name",
            "bytes", "n_transcripts", "n_regions", "n_skipped", "seconds")
    out = dict(zip(cols, row))
    out["species"] = species_key(upload_id)
    return out


def ready(con):
    """Every upload that can be searched right now."""
    return [get(con, r[0]) for r in con.execute(
        "SELECT upload_id FROM uploads WHERE status='ready' "
        "ORDER BY created_at DESC")]


def touch(con, species_key_or_id):
    """Record that an upload was used, so the sweep leaves it alone."""
    uid = species_key_or_id
    if sp.is_upload(uid):
        uid = uid[len(sp.UPLOAD_PREFIX):]
    con.execute("UPDATE uploads SET last_used_at=? WHERE upload_id=?",
                (now(), uid))
    con.commit()


def next_queued(con):
    """Atomically claim the oldest queued upload. Returns an id, or None."""
    row = con.execute("SELECT upload_id FROM uploads WHERE status='queued' "
                      "ORDER BY created_at LIMIT 1").fetchone()
    if row is None:
        return None
    cur = con.execute("UPDATE uploads SET status='running', started_at=? "
                      "WHERE upload_id=? AND status='queued'",
                      (now(), row[0]))
    con.commit()
    return row[0] if cur.rowcount else None


def requeue_stale(con):
    """Put uploads left 'running' by a crashed worker back in the queue."""
    cur = con.execute("UPDATE uploads SET status='queued', started_at=NULL "
                      "WHERE status='running'")
    con.commit()
    return cur.rowcount


def _fail(con, upload_id, message):
    con.execute("UPDATE uploads SET status='failed', finished_at=?, error=? "
                "WHERE upload_id=?", (now(), message, upload_id))
    con.commit()
    raise ValueError(message)


def execute(con, upload_id):
    """Parse the pair and load it. Raises with a readable reason on failure.

    Three things are checked, and each catches a mistake people actually
    make. The messages say what is wrong in plain words, because the
    person reading them has no way to inspect the parse themselves.
    """
    up = get(con, upload_id)
    if up is None:
        raise ValueError("no such upload: " + upload_id)
    row = con.execute("SELECT fasta_path, gtf_path FROM uploads "
                      "WHERE upload_id=?", (upload_id,)).fetchone()
    fasta_path, gtf_path = row
    t0 = time.time()
    key = species_key(upload_id)
    le = _loader()

    try:
        rows, problems, counts = le.build(key, fasta_path, gtf_path)
    except SystemExit as exc:
        # build() exits when the GTF has no canonical transcripts at all.
        _fail(con, upload_id,
              "Could not read the annotation file. %s Ensembl GTFs mark one "
              "transcript per gene with the Ensembl_canonical tag; a GFF3, "
              "a GTF from another source, or a partial download will not "
              "have it." % (str(exc) or ""))
    except Exception as exc:
        _fail(con, upload_id, "Could not parse the files: %r" % (exc,))

    # 1. Do the two files describe the same transcripts at all?
    if counts["gtf"] and not rows and counts["absent"] == counts["gtf"]:
        _fail(con, upload_id,
              "None of the %s transcripts in the annotation were found in "
              "the sequence file. The two files are probably not a matching "
              "pair - they must be the cDNA FASTA and the GTF for the same "
              "assembly and release." % format(counts["gtf"], ","))

    # 2. Did anything survive?
    if len(rows) < MIN_TRANSCRIPTS:
        _fail(con, upload_id,
              "Only %d protein-coding transcripts could be read, which is "
              "too few to search. Check that the sequence file is the cDNA "
              "FASTA (not the ncRNA, CDS or peptide file) and that neither "
              "download was truncated." % len(rows))

    # 3. Do the coordinates agree? A length mismatch means the exon
    #    structure in the GTF does not describe the sequence in the
    #    FASTA, so every position reported downstream would be wrong.
    total = len(rows) + len(problems)
    if total and len(problems) / total > MAX_MISMATCH_FRACTION:
        _fail(con, upload_id,
              "%s of %s transcripts have a different length in the two "
              "files, so they appear to be from different releases. Download "
              "both from the same Ensembl release and try again."
              % (format(len(problems), ","), format(total, ",")))

    try:
        le.load(con, key, rows, fasta_path, gtf_path)
    except Exception as exc:
        _fail(con, upload_id, "Could not store the parsed data: %r" % (exc,))

    con.execute(
        "UPDATE uploads SET status='ready', finished_at=?, last_used_at=?, "
        "n_transcripts=?, n_regions=?, n_skipped=?, seconds=? "
        "WHERE upload_id=?",
        (now(), now(), len(rows), sum(len(r["regions"]) for r in rows),
         counts["absent"] + counts["noncoding"] + len(problems),
         round(time.time() - t0, 2), upload_id))
    con.commit()
    return len(rows)


def delete(con, upload_id):
    """Remove an upload: its rows, its transcripts and its files."""
    key = species_key(upload_id)
    con.execute("DELETE FROM regions WHERE refseq IN "
                "(SELECT refseq FROM transcripts WHERE species=?)", (key,))
    con.execute("DELETE FROM transcripts WHERE species=?", (key,))
    con.execute("DELETE FROM genes WHERE species=?", (key,))
    con.execute("DELETE FROM data_sources WHERE name=?",
                (sp.source_name(key),))
    con.execute("DELETE FROM uploads WHERE upload_id=?", (upload_id,))
    con.commit()
    shutil.rmtree(os.path.join(UPLOAD_DIR, upload_id), ignore_errors=True)


def sweep(con, hours=SWEEP_HOURS):
    """Delete uploads nobody has used for `hours`. Returns how many.

    Idle time, not age: last_used_at is touched every time a job reads
    the upload.
    """
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(
        timespec="seconds")
    stale = [r[0] for r in con.execute(
        "SELECT upload_id FROM uploads WHERE "
        "COALESCE(last_used_at, created_at) < ?", (cutoff,))]
    for upload_id in stale:
        delete(con, upload_id)
    return len(stale)
