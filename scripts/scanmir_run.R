#!/usr/bin/env Rscript
# scanMiR runner, called by src/tools/scanmir_tool.py.
#
# Reads a TSV of transcripts (refseq, cds_end, sequence), scans one miRNA
# against all of them, and writes two TSVs: one row per site, one row per
# transcript.
#
# Nothing here decides policy. Thresholds and flags arrive as arguments so the
# Python side owns them and records them in provenance.
#
# The model is chosen by SEQUENCE, not by name. scanMiRData was built on
# miRBase 22; 864 of its 2,656 human models carry a name that Release 23 has
# since changed, and 243 carry a seed that Release 23 has revised. Matching on
# the mature sequence sidesteps both: a model is used only when it was built
# for the molecule actually being queried.

suppressPackageStartupMessages({
  library(scanMiR)
  library(scanMiRData)
  library(Biostrings)
  library(data.table)
})

a <- commandArgs(trailingOnly = TRUE)
if (length(a) < 7) {
  stop("usage: scanmir_run.R <tx.tsv> <mirna_name> <mirna_seq> <out_sites.tsv> ",
       "<out_agg.tsv> <maxlogkd_utr> <maxlogkd_orf> [shadow]")
}
tx_path   <- a[1]
mir_name  <- a[2]
mir_seq   <- toupper(gsub("U", "T", a[3]))
out_sites <- a[4]
out_agg   <- a[5]
kd_utr    <- as.numeric(a[6])
kd_orf    <- as.numeric(a[7])
shadow    <- if (length(a) >= 8) as.integer(a[8]) else 0L

fail <- function(code, msg) {
  cat(sprintf("STATUS\t%s\t%s\n", code, msg))
  quit(save = "no", status = 0)
}

mods <- getKdModels("hsa")

# --- choose the model ------------------------------------------------------
modseq <- vapply(mods, function(x) toupper(gsub("U", "T", as.character(x$mirseq)[1])),
                 character(1))

exact <- which(modseq == mir_seq)
if (length(exact) >= 1) {
  km  <- mods[[exact[1]]]
  how <- if (names(mods)[exact[1]] == mir_name) "name and sequence agree"
         else sprintf("sequence match (model named %s)", names(mods)[exact[1]])
} else if (mir_name %in% names(mods)) {
  # The name is known but the sequence has changed since the model was built.
  # If the seed changed, the model predicts a different molecule and must not
  # be used. If only the 3' end changed, sites are still found correctly but
  # p3.score is computed from the older sequence.
  km <- mods[[mir_name]]
  ms <- toupper(gsub("U", "T", as.character(km$mirseq)[1]))
  if (substr(ms, 2, 8) != substr(mir_seq, 2, 8)) {
    fail("SEED_CHANGED",
         sprintf("scanMiR model seed %s does not match miRBase R23 seed %s",
                 substr(ms, 2, 8), substr(mir_seq, 2, 8)))
  }
  how <- "name match, 3' end differs from miRBase R23"
} else {
  fail("NO_MODEL", sprintf("no scanMiR KdModel for %s", mir_name))
}

# --- scan ------------------------------------------------------------------
d <- fread(tx_path, header = FALSE, sep = "\t",
           col.names = c("refseq", "cds_end", "sequence"),
           colClasses = c("character", "integer", "character"))
if (nrow(d) == 0) fail("NO_TARGETS", "no transcript sequences supplied")

seqs <- DNAStringSet(d$sequence)
names(seqs) <- d$refseq
# scanMiR models a transcript as ORF followed by 3'UTR and has no concept of a
# 5'UTR, so cds_end (not the CDS length) is what marks where the 3'UTR begins.
# A 5'UTR site therefore takes the ORF penalty; our own regions table still
# classifies it correctly for display.
mcols(seqs)$ORF.length <- d$cds_end

m <- findSeedMatches(seqs, km,
                     shadow       = shadow,
                     maxLogKd     = c(kd_utr, kd_orf),
                     keepMatchSeq = TRUE,
                     verbose      = FALSE)

sites <- as.data.table(as.data.frame(m))
if (nrow(sites) == 0) {
  fwrite(data.table(refseq = character(), start = integer(), end = integer(),
                    type = character(), log_kd = integer(), p3_score = integer(),
                    note = character(), match_seq = character(), orf = logical()),
         out_sites, sep = "\t")
  fwrite(data.table(refseq = character(), repression = numeric()),
         out_agg, sep = "\t")
  cat(sprintf("STATUS\tOK\t%s\n", how))
  cat("MODEL\t", names(mods)[if (length(exact)) exact[1] else which(names(mods) == mir_name)],
      "\n", sep = "")
  cat("SITES\t0\nTRANSCRIPTS\t0\n")
  quit(save = "no", status = 0)
}

setnames(sites, "seqnames", "refseq")
if (!"ORF" %in% names(sites)) sites[, ORF := NA]
if (!"sequence" %in% names(sites)) sites[, sequence := NA_character_]
out <- sites[, .(refseq = as.character(refseq), start, end,
                 type = as.character(type),
                 log_kd = as.integer(log_kd),
                 p3_score = as.integer(p3.score),
                 note = as.character(note),
                 match_seq = as.character(sequence),
                 orf = as.logical(ORF))]
fwrite(out, out_sites, sep = "\t")

# --- aggregate -------------------------------------------------------------
ag <- as.data.table(aggregateMatches(m))
setnames(ag, "transcript", "refseq")
ag[, refseq := as.character(refseq)]
fwrite(ag, out_agg, sep = "\t")

cat(sprintf("STATUS\tOK\t%s\n", how))
cat("MODEL\t", as.character(km$name), "\n", sep = "")
cat("MODEL_SEQ\t", as.character(km$mirseq), "\n", sep = "")
cat("CONSERVATION\t", as.character(km$conservation), "\n", sep = "")
cat("SITES\t", nrow(out), "\n", sep = "")
cat("TRANSCRIPTS\t", nrow(ag), "\n", sep = "")
cat("SCANMIR\t", as.character(packageVersion("scanMiR")), "\n", sep = "")
cat("SCANMIRDATA\t", as.character(packageVersion("scanMiRData")), "\n", sep = "")
cat("RVERSION\t", paste(R.version$major, R.version$minor, sep = "."), "\n", sep = "")
