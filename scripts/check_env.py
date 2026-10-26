#!/usr/bin/env python3
"""Check that everything miRPanel needs is installed and working.

Run this before the first start, and again whenever something fails for a
reason that is not obvious:

    python3 scripts/check_env.py

Every line is a separate check. A FAIL means the tool will not work until
that line is fixed; a WARN means something optional is missing.
"""

import importlib
import os
import shutil
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "data", "processed", "mirna.db")

fails = []
warns = []


def ok(what, detail=""):
    print("  OK    %-34s %s" % (what, detail))


def fail(what, detail=""):
    print("  FAIL  %-34s %s" % (what, detail))
    fails.append(what)


def warn(what, detail=""):
    print("  WARN  %-34s %s" % (what, detail))
    warns.append(what)


print("\nPython")
v = sys.version_info
if v >= (3, 10):
    ok("python", "%d.%d.%d" % (v.major, v.minor, v.micro))
else:
    fail("python", "found %d.%d, need 3.10 or newer" % (v.major, v.minor))

for mod in ("fastapi", "uvicorn", "pydantic", "openpyxl", "multipart"):
    try:
        m = importlib.import_module(mod)
        ok(mod, getattr(m, "__version__", ""))
    except ImportError:
        fail(mod, "pip install -r requirements-lock.txt")

print("\nExternal programs")
rh = shutil.which("RNAhybrid")
if rh:
    ok("RNAhybrid", rh)
else:
    fail("RNAhybrid", "apt install rnahybrid   (the binary is capitalised)")

rs = shutil.which("Rscript")
if rs:
    try:
        out = subprocess.run([rs, "-e", "cat(R.version.string)"],
                             capture_output=True, text=True, timeout=60)
        ok("Rscript", out.stdout.strip() or rs)
    except Exception as e:
        fail("Rscript", "found but would not run: %s" % e)
else:
    fail("Rscript", "apt install r-base")

if shutil.which("docker"):
    ok("docker", "present (needed only to build scanMiR models on demand)")
else:
    warn("docker", "absent; scanMiR works for human, mouse and rat only")

print("\nR packages")
# The versions this release was built and tested against. An older R
# resolves to an older Bioconductor and installs scanMiR 1.4.0 without a
# word, which gives different numbers, so being present is not enough.
R_MIN = "4.5.0"
R_PKGS = [
    ("clusterProfiler", "4.18.4"),
    ("scanMiR", "1.16.0"),
    ("scanMiRData", "1.16.0"),
    ("miRBaseConverter", "1.34.0"),
    ("AnnotationHub", "4.0.0"),
    ("org.Hs.eg.db", "3.22.0"),
    ("org.Mm.eg.db", "3.22.0"),
    ("org.Rn.eg.db", "3.22.0"),
    ("org.Dm.eg.db", "3.22.0"),
]

import shutil as _shutil
import subprocess as _subprocess


def _vtuple(v):
    return tuple(int(x) if x.isdigit() else 0
                 for x in v.replace("-", ".").split("."))


if _shutil.which("Rscript"):
    _script = (
        "writeLines(as.character(getRversion()));"
        "for (p in c(%s)) writeLines(paste(p, tryCatch("
        "as.character(packageVersion(p)), error=function(e) 'MISSING')))"
    ) % ",".join("'%s'" % p for p, _ in R_PKGS)
    try:
        _out = _subprocess.run(["Rscript", "-e", _script], capture_output=True,
                               text=True, timeout=180).stdout.splitlines()
        _rver = _out[0].strip() if _out else "unknown"
        if _vtuple(_rver) >= _vtuple(R_MIN):
            ok("R", _rver)
        else:
            fail("R", "%s is older than %s - see the README" % (_rver, R_MIN))

        _have = {}
        for _line in _out[1:]:
            _bits = _line.split()
            if len(_bits) == 2:
                _have[_bits[0]] = _bits[1]

        for _name, _need in R_PKGS:
            _got = _have.get(_name, "MISSING")
            if _got == "MISSING":
                fail(_name, "not installed - run: Rscript install_r.R")
            elif _vtuple(_got) < _vtuple(_need):
                fail(_name, "%s is older than %s - run: Rscript install_r.R"
                     % (_got, _need))
            else:
                ok(_name, _got)
    except Exception as e:
        fail("R packages", "could not be checked: %s" % e)
else:
    fail("R packages", "skipped, Rscript is missing")

print("\nDatabase")
if not os.path.exists(DB):
    fail("mirna.db", "not at %s - build it with the loader scripts" % DB)
else:
    gb = os.path.getsize(DB) / 1e9
    ok("mirna.db", "%.2f GB" % gb)
    try:
        con = sqlite3.connect(DB)
        for table, least in (("genes", 10000), ("transcripts", 10000),
                             ("mirnas", 10000), ("targetscan", 100000),
                             ("mirtarbase", 10000)):
            try:
                n = con.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
            except sqlite3.Error as e:
                fail(table, str(e))
                continue
            if n >= least:
                ok(table, "%s rows" % format(n, ","))
            else:
                warn(table, "only %s rows; expected at least %s"
                     % (format(n, ","), format(least, ",")))
        sp = [r[0] for r in con.execute("SELECT DISTINCT species FROM genes")]
        ok("organisms loaded", ", ".join(sorted(sp)) or "none")
        cache = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        if cache > 5_000_000:
            warn("cached result rows", "%s - run scripts/prune_jobs.py to "
                 "reclaim disk" % format(cache, ","))
        else:
            ok("cached result rows", format(cache, ","))
        con.close()
    except Exception as e:
        fail("mirna.db", "could not be read: %s" % e)

print("\nDisk")
try:
    st = os.statvfs(ROOT)
    free = st.f_bavail * st.f_frsize / 1e9
    (ok if free > 20 else warn)("free space", "%.1f GB" % free)
except Exception:
    pass

print()
if fails:
    print("%d check(s) failed: %s" % (len(fails), ", ".join(fails)))
    print("miRPanel will not run until these are fixed.")
    sys.exit(1)
if warns:
    print("Everything required is present. %d optional item(s) missing: %s"
          % (len(warns), ", ".join(warns)))
else:
    print("Everything checks out.")
sys.exit(0)
