suppressPackageStartupMessages({
  library(scanMiR); library(scanMiRData); library(Biostrings)
})

seqs <- readDNAStringSet("/tmp/mane_all.fa")
cat("transcripts:", length(seqs), " total nt:", sum(width(seqs)), "\n")

mods <- getKdModels("hsa")

t0 <- Sys.time()
m <- findSeedMatches(seqs, mods[["hsa-miR-21-5p"]],
                     keepMatchSeq = TRUE, verbose = FALSE)
t1 <- Sys.time()

cat("elapsed:", as.numeric(difftime(t1, t0, units = "secs")), "s\n")
cat("sites:", length(m), "\n")

df <- as.data.frame(m)
cat("\nsites by type:\n"); print(table(df$type))
cat("\ntranscripts with >=1 site:", length(unique(df$seqnames)), "\n")
cat("\nlog_kd quantiles:\n"); print(quantile(df$log_kd))

t2 <- Sys.time()
ag <- aggregateMatches(m)
t3 <- Sys.time()
cat("\naggregation:", as.numeric(difftime(t3, t2, units = "secs")), "s\n")
cat("genes in aggregate:", nrow(ag), "\n")
print(head(ag[order(ag$repression), ], 10))
