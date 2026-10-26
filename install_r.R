# The R packages miRPanel needs, at the versions it was built against.
#
#   Rscript install_r.R
#
# Bioconductor is pinned to 3.22 on purpose. Left to choose for itself, an
# older R resolves to an older Bioconductor and installs scanMiR 1.4.0
# instead of 1.16.0 without any warning, which gives different results.
#
# This takes half an hour or more. Several packages compile from source.

BIOC <- "3.22"
MIN_R <- "4.5.0"

want <- c("scanMiR", "scanMiRData", "miRBaseConverter", "AnnotationHub",
          "clusterProfiler",
          "org.Hs.eg.db",   # human
          "org.Mm.eg.db",   # mouse
          "org.Rn.eg.db",   # rat
          "org.Dm.eg.db")   # fly
# rabbit has no OrgDb, so it has no GO or KEGG. That is expected.

# ---- R itself has to be new enough for Bioconductor 3.22 ----------------

if (getRversion() < MIN_R) {
  cat("\nR", as.character(getRversion()), "is too old. Bioconductor", BIOC,
      "needs R", MIN_R, "or newer.\n\n")
  cat("Debian and Ubuntu ship an older R, so install it from CRAN instead:\n\n")
  cat("  sudo apt install -y gpg dirmngr ca-certificates\n")
  cat("  gpg --keyserver keyserver.ubuntu.com --recv-keys B8F25A8A73EACF41\n")
  cat("  gpg --export B8F25A8A73EACF41 | sudo tee /etc/apt/trusted.gpg.d/cran_debian.gpg > /dev/null\n")
  cat("  echo \"deb http://cloud.r-project.org/bin/linux/debian bookworm-cran40/\" |\\\n")
  cat("    sudo tee /etc/apt/sources.list.d/cran.list\n")
  cat("  sudo apt update && sudo apt install -y r-base\n\n")
  cat("On Ubuntu, replace bookworm-cran40 with the line for your release:\n")
  cat("  https://cloud.r-project.org/bin/linux/ubuntu/\n\n")
  quit(save = "no", status = 1)
}

cat("\nR", as.character(getRversion()), "- ok\n")

# ---- somewhere this account can write to ------------------------------
# An ordinary account usually cannot write to R's system library, and a
# script run with Rscript will not offer to make a personal one the way an
# interactive session does - it just stops. So make it here. R finds it on
# its own from then on, because the folder now exists.

if (file.access(.libPaths()[1], 2) != 0) {
  personal <- path.expand(Sys.getenv("R_LIBS_USER"))
  if (!nzchar(personal)) {
    cat("\nCannot write to", .libPaths()[1], "and R_LIBS_USER is not set.\n")
    cat("Run this script with sudo, or set R_LIBS_USER to a folder you own.\n\n")
    quit(save = "no", status = 1)
  }
  dir.create(personal, recursive = TRUE, showWarnings = FALSE)
  .libPaths(c(personal, .libPaths()))
  cat("Installing into your personal library:", personal, "\n")
}

# ---- what is already here ----------------------------------------------

have <- rownames(installed.packages())
need <- setdiff(want, have)

if (length(need) == 0) {
  cat("All", length(want), "packages are already installed.\n\n")
  quit(save = "no", status = 0)
}

cat("To install:", paste(need, collapse = ", "), "\n\n")

if (!requireNamespace("BiocManager", quietly = TRUE)) {
  install.packages("BiocManager", repos = "https://cloud.r-project.org")
}

# pin the release before asking for anything
BiocManager::install(version = BIOC, ask = FALSE, update = FALSE)
BiocManager::install(need, version = BIOC, ask = FALSE, update = FALSE)

# ---- say plainly whether it worked -------------------------------------

have <- rownames(installed.packages())
still <- setdiff(want, have)

cat("\n")
for (p in want) {
  v <- tryCatch(as.character(packageVersion(p)), error = function(e) "MISSING")
  cat(sprintf("  %-18s %s\n", p, v))
}
cat("\n")

if (length(still) == 0) {
  cat("All", length(want), "are installed.\n\n")
} else {
  cat("These did not install:", paste(still, collapse = ", "), "\n\n")
  cat("Look back through the output for the FIRST error, not the last. One\n")
  cat("missing system library knocks out a dozen packages that depend on it,\n")
  cat("and the errors at the end only name the ones that fell over after it.\n\n")
  cat("On Debian or Ubuntu these cover every case we have seen:\n\n")
  cat("  sudo apt install -y build-essential cmake \\\n")
  cat("    libcurl4-openssl-dev libssl-dev libxml2-dev \\\n")
  cat("    libfontconfig1-dev libharfbuzz-dev libfribidi-dev libfreetype6-dev \\\n")
  cat("    libpng-dev libtiff5-dev libjpeg-dev \\\n")
  cat("    libglpk-dev libuv1-dev libcairo2-dev\n\n")
  quit(save = "no", status = 1)
}
