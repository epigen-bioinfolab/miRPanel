# Phase 8 — pathway analysis: how the gene list and background were chosen

Every number here was measured on `job_46def2d032c6` (hsa-miR-21-5p,
transcriptome-wide, four tools). Nothing was chosen by taste.

Enrichment results are quoted from stored runs by id — `enr_3e67cd65200d`
(conserved, 381 genes) and `enr_0ac52b947705` (8mer ∩ conserved, 150 genes) —
so any figure here can be re-queried rather than taken on trust. Both passed
`scripts/validate_enrichment.py`: the database matches the TSV R wrote, and
every p-value can be recomputed from the four integers stored beside it.

## What the denominator actually is

The background is every MANE Select gene, 19,363 of them. That is the set the
tool selected from, and it is **not** the denominator of any single test.
org.Hs.eg.db annotates a different part of it for each ontology, and KEGG
covers about half the genome:

| | Genes tested (n) | Background (N) |
|---|---|---|
| GO: Biological Process | 357 | 17,116 |
| GO: Molecular Function | 362 | 17,807 |
| GO: Cellular Component | 372 | 18,206 |
| KEGG | 190 | 8,516 |

All from the same 381-gene list. This is why the four integers are stored per
term and not once per run, and why a KEGG p-value and a GO p-value are not
comparable quantities. A term absent from KEGG may mean "not enriched" or
"not annotated", and the two cannot be told apart from the p-value alone.

## Gene list sizes (`scripts/enrichment_sets.py`)

Enrichment needs roughly 200–1,500 genes: fewer and nothing reaches
significance, more and everything does.

| Rule | Genes |
|---|---|
| seed: 8mer only | 628 |
| seed: 8mer or 7mer-m8 | 2,545 |
| seed: any 7mer or better | 3,480 |
| seed: any site incl. 6mer | 6,673 |
| seed 7mer+ outside the 3′UTR | 1,244 |
| TargetScan: any score | 2,598 |
| **TargetScan: conserved site** | **381** |
| TargetScan: context++ ≤ −0.30 | 320 |
| RNAhybrid: ΔG ≤ −25 | 1,805 |
| miRTarBase: strong evidence | 124 |
| 8mer **and** TargetScan conserved | 150 |

## Background: every MANE Select gene (19,363), always

The alternative — only genes whose 3′UTR is long enough to hold a site —
was measured and dropped. At ≥50 nt it keeps 18,622 of 19,363 (a 3.8%
difference); at ≥200 nt, 16,510. Too small a change to justify the extra
explanation in a methods section.

This does **not** fix the underlying bias: miRNA targets have long 3′UTRs,
and long-3′UTR genes are enriched for transcription factors and
developmental regulators. Fixing that needs length-matched sampling.
Recorded as a limitation rather than half-fixed.

## Three results

**1. An 8mer alone produces no biology.** 628 genes, all 628 recognised by
org.Hs.eg.db, **zero enriched terms**. A canonical 8mer anywhere in a
transcript is not evidence of function. This is a clean negative result and
worth reporting: it is the downstream counterpart of the site-level
argument for showing four columns instead of one.

**2. Conservation alone gives coherent, correct biology.** 381 genes, all 381
recognised by org.Hs.eg.db, 340 enriched terms. Read from the stored run
`enr_3e67cd65200d`, not from a terminal scrollback:

| GO: Biological Process | Genes | Adjusted p |
|---|---|---|
| mesenchyme development | 29 | 1.9 × 10⁻⁷ |
| stem cell differentiation | 25 | 4.0 × 10⁻⁷ |
| lung morphogenesis | 13 | 4.0 × 10⁻⁷ |
| mesenchymal cell differentiation | 24 | 8.6 × 10⁻⁷ |

| KEGG | Genes | Adjusted p |
|---|---|---|
| **MicroRNAs in cancer** | 17 | 2.2 × 10⁻⁵ |
| MAPK signalling | 21 | 3.6 × 10⁻⁴ |
| pathways regulating stem-cell pluripotency | 13 | 1.3 × 10⁻³ |
| proteoglycans in cancer | 15 | 2.4 × 10⁻³ |
| Ras signalling | 16 | 3.0 × 10⁻³ |

The dominant theme is the mesenchymal and stem-cell programme, and the
strongest pathway in a database that knows nothing about this project is
*MicroRNAs in cancer*. The tool reached that from sequence and conservation
alone, with no knowledge of the literature.

**Correction to an earlier draft of this file.** It named
*epithelial-to-mesenchymal transition* as the leading term at
1.9 × 10⁻⁷, and gave the same p-value for KEGG. Both were wrong: that p
belongs to *mesenchyme development*, and EMT itself sits at 1.8 × 10⁻⁴ with
16 genes — present and consistent, but three orders of magnitude weaker than
claimed. KEGG's best is 2.2 × 10⁻⁵. The error came from reading the wrong row
out of a terminal; every number above is now queried from the database, which
is the reason the database exists.

The EMT family in full, for the record: mesenchymal cell differentiation
(24 genes, 8.6 × 10⁻⁷), cardiac EMT (8, 1.3 × 10⁻⁴), EMT (16, 1.8 × 10⁻⁴),
mesenchymal cell proliferation (8, 5.0 × 10⁻⁴), regulation of EMT
(10, 3.5 × 10⁻³). The signal is real and spread across the family rather than
concentrated in the one term with the famous name.

**3. Intersecting with the 8mer scan adds nothing** (`scripts/enrich_control.py`).

The intersection (150 genes) gave 101 terms, best adjusted p 5.4 × 10⁻⁴.
Ten random 150-gene samples drawn from the same 381 conserved genes gave:

    9, 37, 55, 69, 73, 80, 96, [101 real], 131, 152, 301 terms

The real list ranks 8th of 11. Three random lists beat it, one by an order
of magnitude (3.6 × 10⁻⁵). Empirical p ≈ 0.36. **The seed filter is not
selecting biology; it is only making the list smaller.**

On reflection this is expected, and the earlier reasoning was wrong:
TargetScan's predictions are themselves seed-based, so intersecting them
with our seed scan is not combining independent evidence. It mostly selects
the TargetScan genes whose site happens to be an 8mer.

## A caution that came out of the control

Random 150-gene subsets of the *same* 381 genes produced between **9 and
301** enriched terms — a 33-fold range, with top terms ranging from "ear
development" to "MicroRNAs in cancer".

Enrichment on a few hundred genes is unstable. Two consequences:

- prefer the largest defensible list over the most stringent one
- never read a single enrichment run as a settled result

## Decisions

- **Default gene list: TargetScan conserved sites** when TargetScan ran;
  otherwise the 8mer list, with its limitations stated.
- **Background: every MANE Select gene**, printed on every result.
- Every other rule stays available through the tick boxes, with a live
  count, because a user may legitimately want a different question — for
  example sites outside the 3′UTR (1,244 genes), which no 3′UTR-only tool
  can ask.
- The report always states the rule in words: *"381 genes with a conserved
  TargetScan site, tested against 19,363 MANE Select genes."*

## In R (`R/enrich.R`)

- background passed explicitly; omitting it makes clusterProfiler
  substitute its whole annotation database, which is not the set scanned
- Benjamini–Hochberg, terms kept at adjusted p < 0.05
- all three GO ontologies plus KEGG in one table with a `source` column
- ids returned as gene symbols
- the number of ids the annotation recognises is printed, so "no
  enrichment" can never be confused with "nothing mapped"
- KEGG contacts the KEGG server and is allowed to fail without taking GO
  down with it
- a provenance sidecar records R, clusterProfiler and org.Hs.eg.db versions,
  whether KEGG answered, and when — KEGG is fetched live, so the same gene
  list next year can give different pathways and this is what will explain it

## In the database (`src/enrichment.py`, `src/schema.sql`)

- `enrichment_runs` — one row per analysis: the filter, the gene ids actually
  tested, the background release (`MANE v1.5`, joined from `data_sources`),
  the correction method and cutoffs, and the software versions
- `enrichment_terms` — one row per term, carrying `k`, `n`, `K`, `N` so every
  p-value can be recomputed in any language without R
- nothing is deleted when a job is re-run. `job_finished_at` records what the
  job looked like at the time, so a historical result stays readable and the
  interface derives staleness by comparison instead of by destruction
- a repeat of an identical filter returns the existing run rather than
  spending two minutes recomputing it
