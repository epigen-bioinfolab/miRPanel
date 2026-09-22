suppressPackageStartupMessages(library(data.table))
sm <- fread("/tmp/scanmir_models.tsv")
db <- fread("/tmp/mirnas_hsa.tsv", header=FALSE, sep="\t",
            col.names=c("name","accession","sequence","seed","seed_changed"))
al <- fread("/tmp/mirna_aliases.tsv", header=FALSE, sep="\t",
            col.names=c("alias","accession"))

un <- sm[!name %in% db$name]
cat("unmatched by name:", nrow(un), "\n")

r <- merge(un, al, by.x="name", by.y="alias", all.x=TRUE)
cat("resolved via alias:", sum(!is.na(r$accession)), "\n")
cat("still unresolved:  ", sum(is.na(r$accession)), "\n\n")

z <- merge(r[!is.na(accession)], db, by="accession")
z[, sm_s := substr(sm_seq,2,8)][, db_s := substr(gsub("U","T",toupper(sequence)),2,8)]
cat("of those resolved -- seed identical:", sum(z$sm_s==z$db_s),
    " seed differs:", sum(z$sm_s!=z$db_s), "\n\n")
print(head(r[is.na(accession), .(name)], 15))

cat("\n--- the 62 that resolved to an accession but not to a mature row ---\n")
miss <- r[!is.na(accession)][!accession %in% db$accession]
cat("count:", nrow(miss), "\n")
print(head(miss[, .(name, accession)], 10))
