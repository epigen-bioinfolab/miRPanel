"""Affinity models for miRNAs scanMiRData does not ship.

scanMiRData supplies KdModel collections for human, mouse and rat. Every
other organism, including anything a user uploads, has none, and
scanMiR cannot derive one from a sequence: getKdModel() takes the table
of 12-mer dissociation constants as a required input.

That table comes from the convolutional network of McGeary et al.
(2019), published alongside the paper. This module runs that network on
demand for a miRNA with no shipped model, converts its output into a
KdModel, and keeps the result.

VALIDATED, NOT APPROXIMATED
---------------------------
Regenerating hsa-miR-21-5p through this path and comparing it against
the model scanMiRData ships gave identical results: all 1,024
coefficients equal, Pearson r = 1, maximum difference 0. A model built
here is the same model the authors would have built, not an estimate of
one.

WHY THIS DOES NOT GROW THE TOOL
-------------------------------
The CNN writes one row per possible 12-mer: 438,784 rows, about 34 MB,
per miRNA. Generating rabbit's 579 miRNAs that way would produce 20 GB
of intermediate files.

None of it is kept. The raw table is written to a temporary directory,
converted, and deleted in the same call. Only the finished KdModel is
cached, at a few kilobytes each, so a cache covering every organism
costs a handful of megabytes.

Models are cached by mature SEQUENCE, not by name. A KdModel belongs to
a molecule, not to a species, so a rabbit miRNA whose sequence matches
a human one resolves to the same cache entry - which is correct, and
also why 55% of rabbit miRNAs need no CNN run at all.
"""

import hashlib
import os
import shutil
import subprocess
import tempfile

#: Where finished models live. Small files, kept indefinitely.
CACHE_DIR = os.environ.get(
    "MIRPANEL_KDMODEL_CACHE",
    os.path.join(os.path.expanduser("~"), ".mirpanel", "kdmodels"))

#: The CNN checkout (github.com/kslin/miRNA_models).
CNN_DIR = os.environ.get(
    "MIRPANEL_CNN_DIR",
    os.path.join(os.path.expanduser("~"), "miRNA_models"))

#: Image built from docker/cnn.Dockerfile.
CNN_IMAGE = os.environ.get("MIRPANEL_CNN_IMAGE", "mirpanel-cnn")

#: The CNN's own published weights, inside CNN_DIR.
CNN_WEIGHTS = "cnn/trained_model/model-100"

#: Passed to the CNN as --mirlen, matching the value its own README
#: uses for the published model.
MIRLEN = "10"

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
KD_TO_MODEL = os.path.join(_REPO, "scripts", "kd_to_model.R")


class CNNUnavailable(RuntimeError):
    """The CNN cannot be run here. Not an error in the query itself."""


def _dna(seq):
    return "".join(str(seq).split()).upper().replace("U", "T")


def cache_key(mirseq):
    """Cache filename for a mature sequence."""
    return hashlib.sha1(_dna(mirseq).encode()).hexdigest()[:16] + ".rds"


def cached_path(mirseq):
    return os.path.join(CACHE_DIR, cache_key(mirseq))


def have(mirseq):
    """Is a model for this sequence already built?"""
    return os.path.exists(cached_path(mirseq))


def available():
    """Can a model be built here at all?

    Checked before a job is queued so the interface can say that
    scanMiR is unavailable for a given organism, rather than letting
    the job fail several minutes later.
    """
    if not os.path.isdir(CNN_DIR):
        return False, ("The McGeary CNN is not installed. Clone "
                       "github.com/kslin/miRNA_models to %s." % CNN_DIR)
    weights = os.path.join(CNN_DIR, CNN_WEIGHTS + ".index")
    if not os.path.exists(weights):
        return False, ("The CNN checkout at %s has no trained weights "
                       "at %s." % (CNN_DIR, CNN_WEIGHTS))
    try:
        subprocess.run(["docker", "image", "inspect", CNN_IMAGE],
                       capture_output=True, check=True)
    except FileNotFoundError:
        return False, "Docker is not installed; the CNN runs in a container."
    except subprocess.CalledProcessError:
        return False, ("The image %s has not been built. Run: docker build "
                       "-f docker/cnn.Dockerfile -t %s ."
                       % (CNN_IMAGE, CNN_IMAGE))
    return True, None


def _run_cnn(mirseq, name, workdir, passenger=None):
    """Run the CNN for one miRNA. Returns the path to its Kd table."""
    # The CNN reads its input as a table. The passenger column is
    # required by its parser even when --passenger is not given, so the
    # guide sequence is repeated there when the partner strand is
    # unknown; without the flag the column is never read.
    table = os.path.join(workdir, "mir.txt")
    with open(table, "w") as fh:
        fh.write("mir\tguide_seq\tpass_seq\tguide_family\tpass_family\n")
        fh.write("%s\t%s\t%s\t%s\t%s_pass\n"
                 % (name, _dna(mirseq), _dna(passenger or mirseq),
                    name, name))

    out = os.path.join(workdir, "kds.txt")
    cmd = [
        "docker", "run", "--rm",
        "-u", "%d:%d" % (os.getuid(), os.getgid()),
        "-v", "%s:/cnn:ro" % os.path.abspath(CNN_DIR),
        "-v", "%s:/io" % os.path.abspath(workdir),
        "-w", "/cnn", CNN_IMAGE,
        "python", "cnn/generate_12mer_kds.py",
        "--name", name,
        "--mirdata", "/io/mir.txt",
        "--mirlen", MIRLEN,
        "--load_model", CNN_WEIGHTS,
        "--outfile", "/io/kds.txt",
    ]
    if passenger:
        cmd.insert(cmd.index("--name"), "--passenger")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise CNNUnavailable("the CNN failed: %s"
                             % (proc.stderr.strip()[-400:] or "no output"))
    if not os.path.exists(out):
        raise CNNUnavailable("the CNN wrote no output file")
    return out


def build(mirseq, name="query", passenger=None, force=False):
    """Return the path to a KdModel for this sequence, building if needed.

    Roughly 25 seconds for a sequence never seen before, and instant
    afterwards. The 34 MB intermediate table is deleted before this
    returns, whether the conversion succeeded or not.
    """
    path = cached_path(mirseq)
    if os.path.exists(path) and not force:
        return path

    ok, why = available()
    if not ok:
        raise CNNUnavailable(why)

    os.makedirs(CACHE_DIR, exist_ok=True)
    work = tempfile.mkdtemp(prefix="kdmodel_")
    try:
        kds = _run_cnn(mirseq, name, work, passenger)
        tmp_rds = os.path.join(work, "model.rds")
        proc = subprocess.run(
            ["Rscript", KD_TO_MODEL, kds, _dna(mirseq), name, tmp_rds],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise CNNUnavailable("could not build the model: %s"
                                 % proc.stderr.strip()[-400:])
        # Moved into place only once complete, so an interrupted run
        # cannot leave a half-written model in the cache that later
        # queries would load as if it were valid.
        shutil.move(tmp_rds, path)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return path


def cache_stats():
    """How many models are cached and how much room they take."""
    if not os.path.isdir(CACHE_DIR):
        return {"models": 0, "bytes": 0, "dir": CACHE_DIR}
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".rds")]
    total = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    return {"models": len(files), "bytes": total, "dir": CACHE_DIR}
