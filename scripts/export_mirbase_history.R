# Export every historical human miRNA name -> accession pair from miRBaseConverter.
library(miRBaseConverter)

info <- getAllVersionInfo()
vers <- info$Version[info$Status == "Available"]
out <- list()

for (v in vers) {
  t <- try(getMiRNATable(version = v, species = "hsa"), silent = TRUE)
  if (inherits(t, "try-error") || is.null(t) || nrow(t) == 0) next
  out[[v]] <- data.frame(
    alias     = c(t$Mature1, t$Mature2),
    accession = c(t$Mature1_Acc, t$Mature2_Acc),
    version   = v,
    stringsAsFactors = FALSE)
  cat(v, nrow(t), "\n")
}

d <- do.call(rbind, out)
d <- d[!is.na(d$alias) & !is.na(d$accession) & d$alias != "" & d$accession != "", ]
d <- d[!duplicated(d[, c("alias", "accession")]), ]
write.csv(d, "data/raw/mirbase_history_hsa.csv", row.names = FALSE)
cat("pairs written:", nrow(d), " versions used:", length(out), "\n")
