# scanMiR integration — design and findings

Date: 22 September 2026
Status: evaluation complete, integration not yet started

## Decision

scanMiR is the machine-learning prediction tool for this platform.

### Requirement

The supervisor's instruction was a machine-learning-based predictor that
(a) is widely used and accepted, (b) reports target site positions, (c) reports
a score, (d) works across 5'UTR, CDS and 3'UTR, and (e) integrates with the
MANE Select transcript backbone already loaded here.

### Alternatives considered and rejected

**miRDB (MirTarget V4).** The most widely used ML-based predictor. Rejected
because its published dataset is gene-level and 3'UTR-only: three columns
(miRNA, RefSeq accession, target score 50-100) with no site coordinates.
miRDB's web interface does support unconventional-site search in the coding
region and 5'UTR, but only through single-sequence submission; no bulk dataset
exists. Scraping the web interface was rejected as it would make the platform
depend on a remote server and would destroy the provenance guarantees the
architecture rests on. Attaching miRDB's gene-level score to binding sites
found by this platform's own seed analyser was also rejected as fabricated
attribution.

**TarPmiR.** Random forest trained on CLASH data (Helwak et al. 2013;
18,514 sites, 399 miRNAs), scans whole transcripts, reports site positions and
a probability, and is the prediction engine inside miRWalk. Met every
requirement on paper. Not pursued — software last modified March 2017, with
attendant risk that the trained model would not load under current
scikit-learn.

**TargetNet.** Deep residual network, handles non-canonical sites, code and
pretrained models available. Rejected because it scores candidate target sites
supplied by the caller rather than finding sites itself, which would make the
ML column dependent on this platform's own seed analyser and remove its
independence.

### Why scanMiR

- CNN-derived affinity model from McGeary et al., *Science* 2019, trained on
  RNA bind-n-seq — direct in vitro measurement of miRNA-Argonaute binding
  affinity against random 12-mers. Stronger data provenance than any
  alternative considered.
- Scans arbitrary sequence, so 5'UTR, CDS and 3'UTR are all covered.
- Per-site output with coordinates, site type, predicted KD and 3' pairing
  score.
- Also returns an aggregated per-transcript repression estimate.
- R/Bioconductor, actively maintained; the existing R stack (clusterProfiler,
  org.Hs.eg.db) already provides the runtime.
- Its underlying model was independently evaluated in miRBench
  (*Bioinformatics* 2025) as the most consistent performer across datasets
  (APS 0.71-0.77) — the only one of the three candidates with independent
  benchmark evidence at site level.

### Accuracy caveat, for the Discussion

No benchmark evaluates miRDB, scanMiR and TarPmiR on common data under a
common definition of a target, and the three predict different quantities
(gene-level functionality, site-level affinity, site-level probability
respectively). miRBench further reports that standard benchmark datasets carry
a miRNA frequency class bias that inflates published accuracy figures, and
concluded that no state-of-the-art method consistently outperformed the others.
This supports the platform's existing rule that each tool's native score is
reported separately and no composite score is computed.

## Versions

- scanMiR 1.16.0
- scanMiRData 1.16.0
- Bioconductor 3.22, R 4.5.0
- Additional dependencies pulled in: pwalign 1.6.0, GenomicRanges 1.62.1,
  seqLogo 1.76.0

scanMiRData supplies 2,656 human KdModels.

## Parameters

`findSeedMatches` defaults, with decisions:

| Parameter | Default | Decision |
|---|---|---|
| `maxLogKd` | `c(-1, -1.5)` | keep; see decoding below |
| `onlyCanonical` | FALSE | keep — non-canonical sites are the main addition |
| `shadow` | 0 | keep, and document; TargetScan conventionally uses 15 nt |
| `minDist` | 7 | keep |
| `keepMatchSeq` | FALSE | **set TRUE** — fills the binding-site column |
| `p3.extra` | FALSE | consider TRUE for fuller 3' pairing detail |
| `useTmpFiles` | FALSE | keep; memory was not a constraint |
| `BP` | NULL | not needed at current runtimes |

`aggregateMatches` defaults:

| Parameter | Default | Note |
|---|---|---|
| `a` | 0.007726 | relative concentration of unbound AGO-miRNA |
| `b` | 0.5735 | additional repression per bound AGO |
| `c` | 0.181 | penalty for sites in the ORF region |
| `p3` | 0.051 | additional repression from 3' alignment |
| `coef_utr` | 0 | **keep at 0** |
| `coef_orf` | 0 | **keep at 0** |

The vignette gives the length modifier as

    repression_adj = repression * (1 + f * UTR.length + h * ORF.length)

where `coef_utr` = f and `coef_orf` = h. No fitted values are published in the
package documentation, so both stay disabled and this is stated in the methods.
Setting them by guesswork would be worse than leaving them off.

## Finding 1 — ORF.length must be supplied

`findSeedMatches` accepts an `ORF.length` metadata column on the input
`DNAStringSet`. Without it, scanMiR treats the entire transcript as 3'UTR: the
`c = 0.181` ORF penalty is never applied and coding-region sites are scored as
though they were 3'UTR sites.

Supplying `mcols(seqs)$ORF.length <- cds_end` (not `cds_end - cds_start + 1`)
produces an `ORF` logical column on every returned site.

Verified against PTEN (NM_000314.8; 5'UTR 1-845, CDS 846-2057, 3'UTR
2058-8515): the site at 1377 is flagged `ORF = TRUE`, sites from 2094 onward
`FALSE`. The boundary falls exactly where the `regions` table places it.

**Known distortion.** `ORF.length = cds_end` folds the 5'UTR in with the ORF,
because scanMiR models a transcript as ORF followed by 3'UTR and has no concept
of a 5'UTR. A 5'UTR site therefore receives the ORF penalty and the stricter
cutoff. The platform's own `regions` table still classifies such sites
correctly for display and filtering; only scanMiR's internal scoring is
affected. To be stated in the methods.

## Finding 2 — maxLogKd is c(UTR, ORF)

Supplying `ORF.length` reduced the transcriptome-wide site count for
hsa-miR-21-5p from 117,235 to 88,828 (-24%).

On PTEN the count fell 28 -> 26. The two sites lost were at 1021
(log_kd -1.007) and 1217 (-1.409), both within the CDS; the CDS site at 1377
(-1.638) survived. Both lost sites are weaker than -1.5; the survivor is
stronger.

The vector is therefore **c(3'UTR cutoff, ORF cutoff)** = (-1.0, -1.5). Until
`ORF.length` was supplied, every site was being held to the looser UTR
threshold. Established from measurement, not documentation.

## Finding 3 — performance

Machine: Debian, 12 logical cores. Single-threaded.

| Measure | Value |
|---|---|
| Transcripts scanned | 19,363 (MANE Select) |
| Total sequence | 71,545,627 nt |
| Scan time | 17.2 s |
| Aggregation time | 0.23 s |
| Total wall clock incl. R startup | 22.3 s |

scanMiR sits between the fast tools (~1 s) and RNAhybrid (~4 min). It queues as
an async job like RNAhybrid but needs no parallelism.

Note: `mane_status = 'MANE Select'` returns 19,363 transcripts; the 74 MANE
Plus Clinical entries are excluded. The seed scan covers 19,437. This
discrepancy needs a decision before integration.

## Finding 4 — site composition, hsa-miR-21-5p transcriptome-wide

Without ORF.length (117,235 sites):

| Type | Count |
|---|---|
| 8mer | 666 |
| 7mer-m8 | 2,310 |
| 7mer-a1 | 1,377 |
| wobbled 8mer | 970 |
| wobbled 7mer | 682 |
| g-bulged 8mer | 100 |
| g-bulged 7mer | 155 |
| 6mer | 5,710 |
| g-bulged 6mer | 10 |
| 6mer-m8 | 5,604 |
| 6mer-a1 | 10,540 |
| non-canonical | 89,111 |

With ORF.length supplied: 88,828 sites.

Comparison with the other tools for the same miRNA:

| Tool | Records | Genes/transcripts |
|---|---|---|
| miRTarBase | 1,068 | — |
| TargetScan | 2,598 | — |
| seed | 10,254 | 6,673 |
| RNAhybrid | 45,034 | 17,671 |
| scanMiR | 88,828 | ~17,000 |

scanMiR is now the largest tool by record count.

**Consequence for thresholds.** 17,054 of 19,363 transcripts carry at least one
site — 88% of the transcriptome — and 76% of sites are non-canonical. log_kd
quantiles were 0% -4.957, 25% -1.609, 50% -1.232, 75% -1.090, 100% -1.000:
three quarters of all sites sit within 0.6 of the cutoff.

Three independent thresholds are therefore needed:

1. **Storage** — keep scanMiR's default (-1) and store everything, consistent
   with the principle of storing what cannot be cheaply recomputed.
2. **Display** — the results table must not default to showing all sites, or
   scanMiR will bury the other four tools. Mirror the existing 6mer treatment:
   store, flag, hide weak sites by default, with a toggle.
3. **Set membership for the Venn** — "scanMiR found this gene" must not mean
   88% of the transcriptome, or the figure says nothing. Likely the strictest
   of the three.

All three must be recorded in the provenance block.

## Finding 5 — transcript-length bias in the aggregated score

Spearman correlation between aggregated repression and transcript length,
hsa-miR-21-5p, n = 17,054:

| Condition | rho |
|---|---|
| Without ORF.length | -0.641 |
| With ORF.length | -0.598 |

Before the correction the top-ranked transcript was TTN (109,224 nt), the
longest in the human genome, followed by KCNQ1OT1 (91,667 nt). After supplying
ORF.length, TTN drops out of the top ten entirely — the ORF penalty working as
intended. KCNQ1OT1 remains second: it is non-coding, `cds_end = 0`, so all
91 kb is treated as 3'UTR.

The residual correlation is partly real biology — a transcript with a 6 kb
3'UTR genuinely offers more binding opportunities than one with a 200 nt 3'UTR.
scanMiR is not malfunctioning by reflecting that.

**Handling.** No normalisation, consistent with the platform's standing rule
against score transformation. Instead report two scanMiR numbers side by side:

- `repression` — scanMiR's native aggregated score, length-dependent by design
- best-site `log_kd` — the strongest single site, length-independent

Both sortable, with the arrow convention showing direction. Default ranking on
the results page should be best-site log_kd, since it answers "where is the
strongest binding" rather than "which transcript is longest". The choice must
be stated and switchable.

rho = -0.641 / -0.598 should be quoted in the Discussion.

## Finding 6 — miRBase version coverage

scanMiR's KdModel objects carry the miRNA sequence they were built for
(`mirseq`) and the canonical seed (`canonical.seed`), so the model set can be
checked directly against the miRBase Release 23 matures loaded here, with no
need to know which release scanMiRData was built from.

All 2,656 human models were resolved: 1,792 matched a current Release 23 name
directly, and all 864 remaining names resolved through `mirna_aliases`. Zero
unresolved.

| | Models | Seed valid | Seed changed |
|---|---|---|---|
| Matched by current name | 1,792 | 1,581 | 211 |
| Resolved via alias | 864 | 770 | 32 |
| **Total** | **2,656** | **2,351** | **243** |

Plus 62 models resolving to accessions absent from the Release 23 mature table
— miRNAs retired in that release (e.g. hsa-miR-10394-3p, MIMAT0041620).
2,351 + 243 + 62 = 2,656.

**Two results worth reporting.**

First, the cross-tabulation of the platform's own `seed_changed` flag against
observed scanMiR seed mismatches is perfectly diagonal — 1,581 / 0 / 0 / 211.
The flag predicts every mismatch with no false positives and no misses.

Second, the total of 243 is exactly the number of human seed changes flagged
between miRBase v22 and v23 when the database was built. Two independent
derivations agree exactly. This confirms scanMiRData was built on miRBase 22
and independently validates the seed-change tracking.

Of the 440 models whose full sequence differs from Release 23, only 211 differ
in the seed; the other 229 changed at the 3' end only. Those models find the
correct sites, but `p3.score` is computed from the full sequence and therefore
carries a caveat.

**Usable coverage:** 2,351 valid models, covering roughly 84% of the 2,789
human mature miRNAs in the database.

## Cell conventions for the scanMiR column

Following the platform's existing rules:

- **A value** — a valid model exists and scanMiR ran
- **"—"** — scanMiR ran and found no site above threshold for this gene
- **"N.A."** — no usable model: either `seed_changed = 1` (243 miRNAs, model
  predates the Release 23 seed revision) or no KdModel at all (retired miRNAs
  and those postdating the model set)

The N.A. tooltip should distinguish the two causes.

## Open questions before integration

1. MANE Select (19,363) versus MANE Select + Plus Clinical (19,437) — the seed
   scan uses the larger set. Decide and apply consistently.
2. `shadow` — keep at 0, or adopt TargetScan's 15 nt convention.
3. The three thresholds above — set values and record them in provenance.
4. Whether to store `log_kd` as scanMiR's scaled integer (-2440 = -2.440) or as
   a real number. Recommendation: store the integer as returned, lossless, and
   divide for display; state the scaling in the provenance block.
5. The 12-mer in the `sequence` column is the KD model's context window, not
   the 8-nt match. Confirm the offset from the vignette before drawing it on
   the binding map.
6. Whether `p3.extra = TRUE` is worth the extra output.

## Incidental finding

KCNQ1OT1 (NR_002728.4) is non-coding but is listed as MANE Select in MANE v1.5,
with an empty RefSeq_prot field. Verified against
`data/raw/MANE.v1.5.summary.txt.gz`. The loader reproduces the source
faithfully — this is an edge case in MANE, not a loading error. Worth a
footnote: the 19,363-gene enrichment background is not strictly protein-coding.

## Scripts written during evaluation

Under `scripts/`, exploratory and not part of the pipeline:

- `scanmir_test.R` — parameter defaults, single-transcript scan
- `scanmir_time.R` — 500-transcript timing
- `scanmir_full.R` — transcriptome-wide scan and aggregation
- `scanmir_orf.R` — same with ORF.length supplied
- `scanmir_bias.R` — repression vs length correlation
- `km_inspect.R`, `km_export.R`, `km_compare.R`, `km_alias.R` — KdModel
  coverage analysis

## References

Soutschek M, Gross F, Schratt G, Germain P-L. scanMiR: a biochemically based
toolkit for versatile and efficient microRNA target prediction.
*Bioinformatics*. 2022;38(9):2466-2473.

McGeary SE, Lin KS, Shi CY, Pham TM, Bisaria N, Kelley GM, Bartel DP. The
biochemical basis of microRNA targeting efficacy. *Science*.
2019;366(6472):eaav1741.

## Finding 7 — every site is reported as an 8-nt window

Found when the first integrated job put scanMiR beside the seed analyser on
PDCD4:

| Site | seed | scanMiR |
|---|---|---|
| CDS 6mer | 813 | 812 |
| 3'UTR 6mer | 1952 | 1951 |
| 3'UTR 8mer | 1805 | 1805 |

The 8mer agrees exactly; the 6mers are offset by one. Every scanMiR row in
every run carries `width = 8`, whatever the site type.

So `start`-`end` is a fixed 8-nt frame, not the site itself: a 6mer is a 6-nt
core inside an 8-nt window. Two consequences:

- The binding map would draw every scanMiR site 8 nt wide. Either accept it
  and say so in the legend, or narrow the drawn extent per site type.
- Matching sites between tools needs a tolerance of at least 1 nt, not
  coordinate equality.

This resolves open question 5. The `match_sequence` field is wider still - the
KD model's 12-mer context window - so it does not align 1:1 with `start`-`end`
either, and is stored alongside the raw strings rather than as a site extent.

## Finding 8 — the aggregate counts 3'UTR and ORF sites separately

For PDCD4, scanMiR returned 11 sites, while `aggregateMatches` reported
8mer 1, 7mer 0, 6mer 1, non-canonical 7 - nine - plus ORF.canonical 2.

The per-type counts cover 3'UTR sites only; ORF sites are counted in their own
columns. Summing the first four understates the total, and adding all six is
the correct total only because the two groups are disjoint. The export column
documentation must say this, or a reader will get the arithmetic wrong.

Exported as `n_8mer_sites`, `n_7mer_sites`, `n_6mer_sites`,
`n_noncanonical_sites` (3'UTR) and `n_orf_canonical_sites`,
`n_orf_noncanonical_sites` (ORF).

## Integration, completed 22 September 2026

- `src/tools/scanmir_tool.py` - the tool, following the registry contract
- `scripts/scanmir_run.R` - the runner; holds no policy, all thresholds are
  passed in so the Python side records them in provenance
- `scripts/register_scanmir.py` - writes the scanMiRData row into
  data_sources, reading versions from the installed packages
- `src/tools/registry.py` - scanmir_tool added to DEFAULT_TOOLS
- `src/flatten.py` - the new extra keys added to EXTRA_ORDER

No schema change was needed: the `results` table holds scanMiR's records
unaltered, and `ranking.py` already orders genes by their best site, which is
the length-independent ranking Finding 5 called for.

`slow: True`, so scanMiR is excluded from the default tool set exactly as
RNAhybrid is. A four-gene job takes 5.4 s, almost all of it R startup and
loading 2,656 models; transcriptome-wide is 17 s. The flag is accurate, and
the frontend should pre-tick scanMiR in the tool selector so the default user
experience includes it while the API default stays honest.

Verified on hsa-miR-21-5p against PTEN, BCL2, TPM1 and PDCD4: 56 sites, both
the direct and the queued path producing identical results, and the flattened
export carrying no JSON in any cell.

**Biological check.** PDCD4's strongest site anywhere in that job is an 8mer
at 1805-1812 in the 3'UTR, log Kd -4.563 - the canonical, heavily validated
miR-21 site. The seed analyser puts an 8mer at the same position, RNAhybrid a
site at 1790, and miRTarBase records 59 strong functional experiments. Four
methods converging on one site, reported side by side and not averaged.
