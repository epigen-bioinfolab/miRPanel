suppressPackageStartupMessages({
  library(scanMiR); library(scanMiRData); library(Biostrings); library(data.table)
})

d <- fread("/tmp/mane_orf.tsv", header = FALSE,
           col.names = c("refseq","cds_end","sequence"), sep = "\t")
cat("rows:", nrow(d), "\n")

seqs <- DNAStringSet(d$sequence)
names(seqs) <- d$refseq
mcols(seqs)$ORF.length <- d$cds_end

mods <- getKdModels("hsa")

t0 <- Sys.time()
m <- findSeedMatches(seqs, mods[["hsa-miR-21-5p"]],
                     keepMatchSeq = TRUE, verbose = FALSE)
t1 <- Sys.time()
cat("elapsed:", as.numeric(difftime(t1,t0,units="secs")), "s\n")
cat("sites:", length(m), "\n")

df <- as.data.frame(m)
cat("\ncolumns now:\n"); print(names(df))
cat("\nPTEN sites:\n"); print(df[df$seqnames == "NM_000314.8", ])

ag <- aggregateMatches(m)
ag$len <- setNames(width(seqs), names(seqs))[as.character(ag$transcript)]
cat("\nSpearman rho (repression vs length):",
    cor(ag$repression, ag$len, method="spearman"), "\n")
cat("\ntop 10:\n"); print(head(ag[order(ag$repression), ], 10))
