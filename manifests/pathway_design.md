# Phase 8 — pathway analysis: how the gene list and background were chosen

Every number here was measured on `job_46def2d032c6` (hsa-miR-21-5p,
transcriptome-wide, four tools). Nothing was chosen by taste.

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

**2. Conservation alone gives coherent, correct biology.** 381 genes:

- GO: epithelial-to-mesenchymal transition, mesenchyme development,
  Rac signalling, muscle cell proliferation, cardiocyte differentiation
  (best adjusted p 1.9 × 10⁻⁷)
- KEGG: **MicroRNAs in cancer**, MAPK signalling, Ras signalling,
  proteoglycans in cancer, stem-cell pluripotency (21 KEGG terms)

miR-21 is the canonical EMT and fibrosis miRNA. The tool reached that from
sequence and conservation alone, with no knowledge of the literature.

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
