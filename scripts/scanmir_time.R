suppressPackageStartupMessages({
  library(scanMiR); library(scanMiRData); library(Biostrings)
})

seqs <- readDNAStringSet("/tmp/tx500.fa")
cat("transcripts:", length(seqs), " total nt:", sum(width(seqs)), "\n")

mods <- getKdModels("hsa")

t0 <- Sys.time()
m <- findSeedMatches(seqs, mods[["hsa-miR-21-5p"]],
                     keepMatchSeq = TRUE, verbose = FALSE)
t1 <- Sys.time()

cat("elapsed:", as.numeric(difftime(t1, t0, units = "secs")), "s\n")
cat("sites:", length(m), "\n")
print(head(as.data.frame(m), 3))
