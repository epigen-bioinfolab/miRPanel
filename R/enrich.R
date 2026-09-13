#!/usr/bin/env Rscript
# GO and KEGG over-representation for one gene list.
#
#   Rscript R/enrich.R genes.txt background.txt out.tsv
#
# genes.txt      Entrez ids, one per line - the selected targets
# background.txt Entrez ids, one per line - every gene that could have been
#                selected. Enrichment is meaningless without it: leave it out
#                and clusterProfiler silently uses the whole annotation, which
#                is not the set this tool actually scanned.
# out.tsv        one row per enriched term, GO and KEGG together
#
# Choices made here, so the report can state them:
#   - Benjamini-Hochberg correction for multiple testing
#   - a term is kept at adjusted p < 0.05
#   - all three GO ontologies (BP, MF, CC), each corrected within itself by
#     clusterProfiler, plus KEGG
#   - gene ids are translated back to symbols for reading

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3)
  stop("usage: enrich.R genes.txt background.txt out.tsv [meta.tsv]")

suppressPackageStartupMessages({
  library(clusterProfiler)
  library(org.Hs.eg.db)
})

genes      <- unique(readLines(args[1]))
background <- unique(readLines(args[2]))
outfile    <- args[3]

genes      <- genes[nzchar(genes)]
background <- background[nzchar(background)]
if (!length(genes))      stop("the gene list is empty")
if (!length(background)) stop("the background is empty")
if (!all(genes %in% background))
  warning(sum(!genes %in% background), " selected genes are not in the background")

message(sprintf("%d genes against a background of %d", length(genes),
                length(background)))

# How many ids the annotation actually recognises. Genes it does not know are
# dropped silently, so an empty result can mean "no enrichment" or "nothing
# mapped" - two very different things.
known <- keys(org.Hs.eg.db, keytype = "ENTREZID")
message(sprintf("annotation knows %d of %d selected genes and %d of %d background genes",
                sum(genes %in% known), length(genes),
                sum(background %in% known), length(background)))

empty <- function(src) data.frame(source = character(), term_id = character(),
  description = character(), gene_ratio = character(), bg_ratio = character(),
  p_value = numeric(), p_adjust = numeric(), q_value = numeric(),
  n_genes = integer(), genes = character(), stringsAsFactors = FALSE)

as_rows <- function(res, src) {
  if (is.null(res)) return(empty(src))
  df <- as.data.frame(res)
  if (!nrow(df)) return(empty(src))
  ont <- if ("ONTOLOGY" %in% names(df)) paste0("GO:", df$ONTOLOGY) else src
  data.frame(source = ont, term_id = df$ID, description = df$Description,
             gene_ratio = df$GeneRatio, bg_ratio = df$BgRatio,
             p_value = df$pvalue, p_adjust = df$p.adjust,
             q_value = if ("qvalue" %in% names(df)) df$qvalue else NA_real_,
             n_genes = df$Count, genes = df$geneID,
             stringsAsFactors = FALSE)
}

go <- tryCatch(
  enrichGO(gene = genes, universe = background, OrgDb = org.Hs.eg.db,
           keyType = "ENTREZID", ont = "ALL", pAdjustMethod = "BH",
           pvalueCutoff = 0.05, qvalueCutoff = 0.2, readable = TRUE),
  error = function(e) { message("GO failed: ", conditionMessage(e)); NULL })

# KEGG asks the KEGG server for its pathway definitions, so this step needs
# a working network connection. It is allowed to fail without taking GO down.
kegg <- tryCatch({
  k <- enrichKEGG(gene = genes, universe = background, organism = "hsa",
                  pAdjustMethod = "BH", pvalueCutoff = 0.05)
  if (!is.null(k)) k <- setReadable(k, org.Hs.eg.db, keyType = "ENTREZID")
  k
}, error = function(e) { message("KEGG failed: ", conditionMessage(e)); NULL })

out <- rbind(as_rows(go, "GO"), as_rows(kegg, "KEGG"))
out <- out[order(out$p_adjust, out$p_value), ]

write.table(out, outfile, sep = "\t", quote = FALSE, row.names = FALSE,
            na = "")

# Provenance for the database: versions, how many ids the annotation knew, and
# when KEGG was fetched - KEGG is pulled live, so the same list next year can
# give different pathways and this is what explains it.
if (length(args) >= 4) {
  writeLines(c(
    paste0("r_version\t", paste(R.version$major, R.version$minor, sep = ".")),
    paste0("clusterprofiler_version\t",
           as.character(utils::packageVersion("clusterProfiler"))),
    paste0("orgdb_version\t",
           as.character(utils::packageVersion("org.Hs.eg.db"))),
    paste0("n_genes\t", length(genes)),
    paste0("n_genes_annotated\t", sum(genes %in% known)),
    paste0("n_background\t", length(background)),
    paste0("n_background_annotated\t", sum(background %in% known)),
    paste0("kegg_ok\t", as.integer(!is.null(kegg))),
    paste0("kegg_fetched_at\t", format(Sys.time(), "%Y-%m-%dT%H:%M:%S")),
    paste0("n_terms\t", nrow(out))), args[4])
}
message(sprintf("%d enriched terms written to %s", nrow(out), outfile))
if (nrow(out)) print(utils::head(out[, c("source", "term_id", "description",
                                         "n_genes", "p_adjust")], 10))
