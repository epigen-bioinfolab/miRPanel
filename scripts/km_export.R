suppressPackageStartupMessages({library(scanMiR);library(scanMiRData);library(data.table)})
mods <- getKdModels("hsa")
g <- function(f) vapply(mods, function(x) as.character(x[[f]])[1], character(1))
sm <- data.table(name=names(mods),
                 sm_seq=gsub("U","T",toupper(g("mirseq"))),
                 sm_seed=g("canonical.seed"),
                 cons=g("conservation"))
fwrite(sm, "/tmp/scanmir_models.tsv", sep="\t")
cat("models:", nrow(sm), "\n"); print(head(sm, 3))
