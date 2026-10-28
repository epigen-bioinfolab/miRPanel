#!/bin/bash
# miRPanel installer. Run it from the folder you cloned into:
#
#   ./install.sh
#
# It checks what is needed, sets up a virtual environment, downloads the
# reference database, and verifies the result. Safe to run again.

set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1

VERSION="v0.1.0"
ARCHIVE="mirpanel-data-${VERSION}.tar.gz"
DATA_URL="https://github.com/epigen-bioinfolab/miRPanel/releases/download/${VERSION}/${ARCHIVE}"
DATA_SHA="3dbe163f614058cf4af670ea69542cf52c78b8a8eac96b5106c2eb440a7a2373"

DB="data/processed/mirna.db"
MANE="data/raw/MANE.GRCh38.v1.5.refseq_rna.gbff.gz"

MIN_R="4.5.0"
R_PKGS="scanMiR scanMiRData miRBaseConverter AnnotationHub clusterProfiler org.Hs.eg.db org.Mm.eg.db org.Rn.eg.db org.Dm.eg.db"

SYS_LIBS="build-essential cmake \\
    libcurl4-openssl-dev libssl-dev libxml2-dev \\
    libfontconfig1-dev libharfbuzz-dev libfribidi-dev libfreetype6-dev \\
    libpng-dev libtiff5-dev libjpeg-dev \\
    libglpk-dev libuv1-dev libcairo2-dev"

MISSING=0

hr(){ printf '\n%s\n' "----------------------------------------------------"; }
ok(){ printf '  ok      %s\n' "$1"; }
no(){ printf '  missing %s\n' "$1"; MISSING=1; }
note(){ printf '          %s\n' "$1"; }

printf '\n miRPanel installer\n'

# ---------------------------------------------------------------- python
hr; printf ' Python\n\n'

if ! command -v python3 >/dev/null 2>&1; then
  no "python3"
  note "sudo apt install python3 python3-venv python3-pip"
else
  PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
    ok "python3 $PYV"
  else
    no "python3 $PYV is too old, 3.10 or newer is needed"
  fi
  if ! python3 -c 'import venv' >/dev/null 2>&1; then
    no "python3-venv"
    note "sudo apt install python3-venv"
  fi
fi

# ------------------------------------------------------ external programs
hr; printf ' External programs\n\n'

if command -v RNAhybrid >/dev/null 2>&1; then
  ok "RNAhybrid  $(command -v RNAhybrid)"
else
  no "RNAhybrid"
  note "sudo apt install rnahybrid"
  note "the binary is RNAhybrid, with a capital R and H"
fi

for prog in sqlite3 curl tar gzip; do
  if command -v "$prog" >/dev/null 2>&1; then
    ok "$prog"
  else
    no "$prog"
    note "sudo apt install $prog"
  fi
done

if command -v docker >/dev/null 2>&1; then
  ok "docker     (optional, builds scanMiR models on demand)"
else
  note "docker is not installed. Optional: it is only needed to build a"
  note "scanMiR model for an organism that has none yet."
fi

# ----------------------------------------------------------------------- R
hr; printf ' R\n\n'

R_OK=0
if ! command -v Rscript >/dev/null 2>&1; then
  no "Rscript"
  note "see the R section below"
else
  RVER=$(R --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  if [ -n "$RVER" ] && \
     [ "$(printf '%s\n%s\n' "$RVER" "$MIN_R" | sort -V | head -1)" = "$MIN_R" ]; then
    ok "R $RVER"
    R_OK=1
  else
    no "R ${RVER:-unknown} is too old, $MIN_R or newer is needed"
  fi
fi

if [ "$R_OK" -eq 0 ]; then
  note ""
  note "Debian and Ubuntu ship an older R than Bioconductor 3.22 needs."
  note "Installing it from the distribution gives scanMiR 1.4.0 instead of"
  note "1.16.0, with no warning and different results. Use CRAN's own"
  note "repository:"
  note ""
  note "  sudo apt install -y gpg dirmngr ca-certificates"
  note "  gpg --keyserver keyserver.ubuntu.com --recv-keys B8F25A8A73EACF41"
  note "  gpg --export B8F25A8A73EACF41 | sudo tee \\"
  note "    /etc/apt/trusted.gpg.d/cran_debian.gpg > /dev/null"
  note "  echo \"deb http://cloud.r-project.org/bin/linux/debian bookworm-cran40/\" |\\"
  note "    sudo tee /etc/apt/sources.list.d/cran.list"
  note "  sudo apt update && sudo apt install -y r-base"
  note ""
  note "On Ubuntu use the line for your release from"
  note "  https://cloud.r-project.org/bin/linux/ubuntu/"
fi

# ------------------------------------------------------------ R packages
hr; printf ' R packages\n\n'

if [ "$R_OK" -eq 1 ]; then
  R_MISSING=$(Rscript -e "
    want <- strsplit('$R_PKGS', ' ')[[1]]
    cat(paste(setdiff(want, rownames(installed.packages())), collapse=' '))
  " 2>/dev/null)

  if [ -z "$R_MISSING" ]; then
    ok "all nine Bioconductor packages are installed"
  else
    no "R packages: $R_MISSING"
    note ""
    note "These compile from source and need development libraries that a"
    note "minimal Debian or Ubuntu does not have. Install them first, or the"
    note "build fails with errors naming packages that are not the problem:"
    note ""
    note "  sudo apt install -y $SYS_LIBS"
    note ""
    note "then:  Rscript install_r.R"
    note "which takes half an hour or more."
  fi
else
  note "skipped, because R is missing or too old"
fi

# ------------------------------------------------------------------ stop
if [ "$MISSING" -ne 0 ]; then
  hr
  printf '\n Sort out what is listed above, then run ./install.sh again.\n\n'
  exit 1
fi

# ------------------------------------------------------- virtualenv, pip
hr; printf ' Python packages\n\n'

# A venv carries absolute paths, so one copied or moved from elsewhere
# looks present but does not run. Activating it silently does nothing and
# pip then hits the system Python, which Debian refuses.
if [ -d venv ] && ! venv/bin/python3 -c "import sys" >/dev/null 2>&1; then
  printf '  the existing venv does not work here, rebuilding it\n'
  rm -rf venv
fi

if [ ! -d venv ]; then
  printf '  creating venv\n'
  python3 -m venv venv || exit 1
fi

# shellcheck disable=SC1091
. venv/bin/activate

printf '  installing from requirements.txt\n\n'
pip install --quiet --upgrade pip || exit 1
pip install --quiet -r requirements.txt || {
  printf '\n  pip failed. The error above says why.\n\n'
  exit 1
}
ok "done"

# ------------------------------------------------------------------ data
hr; printf ' Reference database\n\n'

mkdir -p data/processed data/raw data/uploads data/tmp dist

if [ -f "$DB" ] && [ -f "$MANE" ]; then
  ok "already present, skipping the download"
else
  printf '  downloading %s (588 MB)\n' "$ARCHIVE"
  printf '  this is a one-off, and it resumes if interrupted\n\n'

  curl -L -C - --fail --progress-bar -o "dist/$ARCHIVE" "$DATA_URL" || {
    printf '\n  the download failed. Check your connection and run this again.\n\n'
    exit 1
  }

  printf '\n  checking the file is intact\n'
  GOT=$(sha256sum "dist/$ARCHIVE" | cut -d" " -f1)
  if [ "$GOT" != "$DATA_SHA" ]; then
    printf '\n  the download is damaged and has not been unpacked.\n'
    printf '  expected %s\n' "$DATA_SHA"
    printf '  found    %s\n' "$GOT"
    printf '\n  delete dist/%s and run ./install.sh again.\n\n' "$ARCHIVE"
    exit 1
  fi
  ok "intact"

  printf '  unpacking\n'
  tar -xzf "dist/$ARCHIVE" -C data || exit 1
  ok "unpacked"

  printf '\n  dist/%s can be deleted to free 588 MB.\n' "$ARCHIVE"
fi

# ----------------------------------------------------------------- check
hr; printf ' Checking the installation\n'

python3 scripts/check_env.py
RC=$?

hr
if [ "$RC" -eq 0 ]; then
  printf '\n Installed. Start it with:\n\n   ./launch.sh\n\n'
  printf ' Then open http://localhost:8000\n\n'
else
  printf '\n Something above is not right. Fix it and run ./install.sh again.\n\n'
fi
exit "$RC"
