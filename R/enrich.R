#!/usr/bin/env Rscript
# GO and KEGG over-representation for one gene list, in any organism.
#
#   Rscript R/enrich.R genes.tsv background.tsv out.tsv meta.tsv \
#                      <orgdb_pkg|""> <latin name> <kegg code>
#
# genes.tsv       two columns: gene id and symbol, one gene per line
# background.tsv  the same, for every gene that could have been selected
# out.tsv         one row per enriched term, GO and KEGG together
# meta.tsv        provenance: versions, how much mapped, when KEGG was fetched
#
# The background matters. Without it clusterProfiler quietly uses the whole
# annotation, which is not the set this tool scanned.
#
# Choices made here, so the report can state them:
#   - Benjamini-Hochberg correction
#   - a term is kept at adjusted p < 0.05
#   - all three GO ontologies, each corrected within itself, plus KEGG
#   - ids are translated back to symbols for reading
#
# WHY THE ID MAPPING IS NOT FIXED
# -------------------------------
# Human genes are stored as Entrez ids and need no translation. Every other
# organism is loaded from Ensembl, which carries no Entrez id, so the stored
# id is an Ensembl one and has to be mapped before enrichment can run.
#
# Which key maps best differs by organism. Mouse and fly map completely by
# either Ensembl id or symbol. Rabbit maps only 48% by Ensembl id but 65% by
# alias. So all three keys are tried and the best kept, and both the key used
# and the fraction mapped are written to meta.tsv - a rabbit run that covers
# two thirds of its genes should say so rather than look complete.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4)
  stop("usage: enrich.R genes.tsv background.tsv out.tsv meta.tsv ",
       "[orgdb_pkg] [latin] [kegg]")

outfile   <- args[3]
metafile  <- args[4]
orgdb_pkg <- if (length(args) >= 5) args[5] else "org.Hs.eg.db"
latin     <- if (length(args) >= 6) args[6] else "Homo sapiens"
kegg_code <- if (length(args) >= 7 && nzchar(args[7])) args[7] else "hsa"

suppressPackageStartupMessages({
  library(clusterProfiler)
  library(AnnotationDbi)
})

read_pairs <- function(path) {
  d <- read.delim(path, header = FALSE, stringsAsFactors = FALSE,
                  col.names = c("id", "symbol"), quote = "")
  d <- d[nzchar(d$id), , drop = FALSE]
  d[!duplicated(d$id), , drop = FALSE]
}

genes_in <- read_pairs(args[1])
bg_in    <- read_pairs(args[2])
if (!nrow(genes_in)) stop("the gene list is empty")
if (!nrow(bg_in))    stop("the background is empty")

# --- the annotation database ------------------------------------------------
# A local package where one exists, otherwise AnnotationHub, which carries
# OrgDbs for roughly 2,000 species built from NCBI's own annotation.
orgdb_version <- NA_character_
if (nzchar(orgdb_pkg)) {
  suppressPackageStartupMessages(library(orgdb_pkg, character.only = TRUE))
  db <- get(orgdb_pkg)
  orgdb_version <- as.character(utils::packageVersion(orgdb_pkg))
  orgdb_source  <- orgdb_pkg
} else {
  suppressPackageStartupMessages(library(AnnotationHub))
  ah  <- AnnotationHub()
  hit <- query(ah, c("OrgDb", latin))
  if (!length(hit))
    stop(sprintf("no annotation database for %s; GO enrichment is not ",
                 latin), "possible for this organism")
  pick <- names(hit)[length(hit)]          # newest record
  db <- ah[[pick]]
  orgdb_source  <- paste0("AnnotationHub ", pick)
  orgdb_version <- pick
}
message("annotation: ", orgdb_source)

# --- map stored ids to Entrez ----------------------------------------------
to_entrez <- function(d, keytype, col) {
  k <- unique(d[[col]])
  k <- k[nzchar(k)]
  if (!length(k) || !(keytype %in% keytypes(db))) return(NULL)
  m <- tryCatch(suppressMessages(
         AnnotationDbi::select(db, keys = k, keytype = keytype,
                               columns = "ENTREZID")),
       error = function(e) NULL)
  if (is.null(m)) return(NULL)
  m[!is.na(m$ENTREZID), c(keytype, "ENTREZID")]
}

# Already Entrez: nothing to do. Recognised by the ids being all digits.
looks_entrez <- function(v) all(grepl("^[0-9]+$", v[seq_len(min(50, length(v)))]))

ROUTES <- list(c("ENTREZID", "id"), c("ENSEMBL", "id"),
               c("SYMBOL", "symbol"), c("ALIAS", "symbol"))

best_key <- "ENTREZID"
if (looks_entrez(genes_in$id)) {
  genes <- unique(genes_in$id)
  bg    <- unique(bg_in$id)
  mapped_frac <- 1
} else {
  best <- NULL; best_n <- -1
  for (r in ROUTES) {
    m <- to_entrez(bg_in, r[1], r[2])
    n <- if (is.null(m)) 0 else length(unique(m[[r[1]]]))
    message(sprintf("  %-9s maps %d of %d background genes",
                    r[1], n, nrow(bg_in)))
    if (n > best_n) { best_n <- n; best <- r }
  }
  best_key <- best[1]
  bgm <- to_entrez(bg_in, best[1], best[2])
  gm  <- to_entrez(genes_in, best[1], best[2])
  if (is.null(bgm) || !nrow(bgm)) stop("no background gene could be mapped")
  bg    <- unique(bgm$ENTREZID)
  genes <- if (is.null(gm)) character(0) else unique(gm$ENTREZID)
  mapped_frac <- best_n / nrow(bg_in)
  message(sprintf("using %s; %.1f%% of the background mapped",
                  best_key, 100 * mapped_frac))
}

if (!length(genes)) stop("none of the selected genes could be mapped")
genes <- genes[genes %in% bg]

message(sprintf("%d genes against a background of %d", length(genes), length(bg)))

known <- keys(db, keytype = "ENTREZID")

empty <- function() data.frame(source = character(), term_id = character(),
  description = character(), gene_ratio = character(), bg_ratio = character(),
  p_value = numeric(), p_adjust = numeric(), q_value = numeric(),
  n_genes = integer(), genes = character(), stringsAsFactors = FALSE)

as_rows <- function(res, src) {
  if (is.null(res)) return(empty())
  df <- as.data.frame(res)
  if (!nrow(df)) return(empty())
  ont <- if ("ONTOLOGY" %in% names(df)) paste0("GO:", df$ONTOLOGY) else src
  data.frame(source = ont, term_id = df$ID, description = df$Description,
             gene_ratio = df$GeneRatio, bg_ratio = df$BgRatio,
             p_value = df$pvalue, p_adjust = df$p.adjust,
             q_value = if ("qvalue" %in% names(df)) df$qvalue else NA_real_,
             n_genes = df$Count, genes = df$geneID,
             stringsAsFactors = FALSE)
}

go <- tryCatch(
  enrichGO(gene = genes, universe = bg, OrgDb = db,
           keyType = "ENTREZID", ont = "ALL", pAdjustMethod = "BH",
           pvalueCutoff = 0.05, qvalueCutoff = 0.2, readable = TRUE),
  error = function(e) { message("GO failed: ", conditionMessage(e)); NULL })

# KEGG fetches its pathway definitions from the KEGG server, so this step
# needs a network connection. It may fail without taking GO down with it.
kegg <- tryCatch({
  k <- enrichKEGG(gene = genes, universe = bg, organism = kegg_code,
                  pAdjustMethod = "BH", pvalueCutoff = 0.05)
  if (!is.null(k)) k <- setReadable(k, db, keyType = "ENTREZID")
  k
}, error = function(e) { message("KEGG failed: ", conditionMessage(e)); NULL })

out <- rbind(as_rows(go, "GO"), as_rows(kegg, "KEGG"))
out <- out[order(out$p_adjust, out$p_value), ]
write.table(out, outfile, sep = "\t", quote = FALSE, row.names = FALSE, na = "")

writeLines(c(
  paste0("r_version\t", paste(R.version$major, R.version$minor, sep = ".")),
  paste0("clusterprofiler_version\t",
         as.character(utils::packageVersion("clusterProfiler"))),
  paste0("orgdb_version\t", orgdb_version),
  paste0("orgdb_source\t", orgdb_source),
  paste0("id_key\t", best_key),
  paste0("mapped_fraction\t", sprintf("%.4f", mapped_frac)),
  paste0("kegg_organism\t", kegg_code),
  paste0("n_input\t", nrow(genes_in)),
  paste0("n_genes\t", length(genes)),
  paste0("n_genes_annotated\t", sum(genes %in% known)),
  paste0("n_background\t", length(bg)),
  paste0("n_background_annotated\t", sum(bg %in% known)),
  paste0("kegg_ok\t", as.integer(!is.null(kegg))),
  paste0("kegg_fetched_at\t", format(Sys.time(), "%Y-%m-%dT%H:%M:%S")),
  paste0("n_terms\t", nrow(out))), metafile)

message(sprintf("%d enriched terms written to %s", nrow(out), outfile))
if (nrow(out)) print(utils::head(out[, c("source", "term_id", "description",
                                         "n_genes", "p_adjust")], 10))
