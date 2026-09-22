suppressPackageStartupMessages({
  library(scanMiR); library(scanMiRData); library(Biostrings)
})
seqs <- readDNAStringSet("/tmp/mane_all.fa")
mods <- getKdModels("hsa")
m  <- findSeedMatches(seqs, mods[["hsa-miR-21-5p"]], verbose = FALSE)
ag <- aggregateMatches(m)

len <- setNames(width(seqs), names(seqs))
ag$len <- len[as.character(ag$transcript)]

cat("Spearman rho (repression vs length):",
    cor(ag$repression, ag$len, method = "spearman"), "\n")
cat("n =", nrow(ag), "\n")
