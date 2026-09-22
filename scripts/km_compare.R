suppressPackageStartupMessages(library(data.table))
sm <- fread("/tmp/scanmir_models.tsv")
db <- fread("/tmp/mirnas_hsa.tsv", header=FALSE, sep="\t",
            col.names=c("name","accession","sequence","seed","seed_changed"))
db[, db_seq := gsub("U","T",toupper(sequence))]
x <- merge(sm, db, by="name", all.x=TRUE)
cat("models:", nrow(sm), " matched:", sum(!is.na(x$db_seq)),
    " unmatched:", sum(is.na(x$db_seq)), "\n")
y <- x[!is.na(db_seq)]
y[, sm_s := substr(sm_seq,2,8)][, db_s := substr(db_seq,2,8)]
cat("seq identical:", sum(y$sm_seq==y$db_seq),
    " seq differs:", sum(y$sm_seq!=y$db_seq), "\n")
cat("seed identical:", sum(y$sm_s==y$db_s),
    " seed differs:", sum(y$sm_s!=y$db_s), "\n\n")
print(table(seed_changed=y$seed_changed, seed_differs=y$sm_s!=y$db_s))
