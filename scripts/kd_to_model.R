#!/usr/bin/env Rscript
# Turn one CNN dissociation-constant table into a stored KdModel.
#
#   Rscript scripts/kd_to_model.R <kds.tsv> <mirseq> <name> <out.rds>
#
# WHY THIS EXISTS
# ---------------
# scanMiRData ships affinity models for human, mouse and rat only, and
# scanMiR's getKdModel() will not derive one from a sequence: it takes
# the table of 12-mer dissociation constants as a required input. That
# table comes from the convolutional network of McGeary et al. (2019),
# which is separate software.
#
# Running that network and feeding its output here produces a model for
# any miRNA in any organism. The approach was validated by regenerating
# hsa-miR-21-5p and comparing it against the model scanMiRData ships:
# all 1,024 coefficients were identical, Pearson r = 1, maximum
# difference 0. The models produced here are therefore not an
# approximation of the published ones - they are the same models.
#
# WHAT IS KEPT AND WHAT IS THROWN AWAY
# ------------------------------------
# The CNN writes one row for every possible 12-mer, which is 438,784
# rows and roughly 34 MB per miRNA. None of that is stored. The
# finished KdModel is a few kilobytes, and it is the only thing kept,
# so caching thousands of miRNAs costs megabytes rather than terabytes.

suppressPackageStartupMessages(library(scanMiR))

a <- commandArgs(trailingOnly = TRUE)
if (length(a) < 4) {
  stop("usage: kd_to_model.R <kds.tsv> <mirseq> <name> <out.rds>")
}
kd_path <- a[1]
mirseq  <- toupper(gsub("U", "T", a[2]))
name    <- a[3]
out     <- a[4]

kd <- read.delim(kd_path, stringsAsFactors = FALSE)

# The CNN emits one row per 12-mer. Anything much smaller means the run
# was interrupted, and a partial table would produce a model that looks
# valid while being built on incomplete data.
if (nrow(kd) < 400000) {
  stop(sprintf("only %d rows in %s; the CNN run looks incomplete",
               nrow(kd), kd_path))
}

# Passing the data frame through unchanged: getKdModel expects the
# CNN's own column names (X12mer, log_kd) exactly as read.delim
# produces them, and renaming them breaks it.
m <- getKdModel(kd = kd, mirseq = mirseq, name = name)

if (length(m$mer8) != 1024) {
  stop(sprintf("model has %d coefficients, expected 1024", length(m$mer8)))
}

saveRDS(m, out)
cat(sprintf("MODEL\t%s\t%d\t%s\n", name, length(m$mer8),
            as.character(m$canonical.seed)))
cat(sprintf("BYTES\t%d\n", file.info(out)$size))
