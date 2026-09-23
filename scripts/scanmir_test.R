suppressPackageStartupMessages({
  library(scanMiR)
  library(scanMiRData)
  library(Biostrings)
})

cat("scanMiR:", as.character(packageVersion("scanMiR")), "\n")
cat("scanMiRData:", as.character(packageVersion("scanMiRData")), "\n\n")

cat("--- findSeedMatches arguments and defaults ---\n")
print(formals(findSeedMatches))

cat("\n--- aggregateMatches arguments and defaults ---\n")
print(formals(aggregateMatches))

mods <- getKdModels("hsa")
s <- readLines("/tmp/pten_seq.txt")
seq <- DNAStringSet(c(PTEN = s[1]))

m <- findSeedMatches(seq, mods[["hsa-miR-21-5p"]], verbose = FALSE)

cat("\n--- site count ---\n")
print(length(m))

cat("\n--- aggregateMatches ---\n")
ag <- aggregateMatches(m)
print(ag)
