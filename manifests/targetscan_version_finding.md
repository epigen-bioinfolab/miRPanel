# TargetScan v8.0 vs miRBase: version reconciliation

Measured 2026-09-07 with `scripts/targetscan_basis.py` and
`scripts/check_targetscan_join.py`.

## Question

TargetScan predictions are precomputed against a fixed miRBase release.
Our database uses miRBase Release 23. Do they agree, and where they do
not, is the disagreement fully accounted for?

## Which release TargetScan v8.0 uses

TargetScan human rows: 2606, in 2064 distinct seed families.

| Reference | seeds identical | seeds different | accession absent |
|---|---|---|---|
| miRBase R22 (2656 human) | 2550 | 4 | 52 |
| miRBase R23 (2789 human) | 2264 | 238 | 104 |

Agreement with R22 is 2550/2554 = 99.84% where comparable.
TargetScan v8.0 is a miRBase v22-era resource.

## Mechanism of disagreement

Every seed difference is 5' end re-annotation, not a different miRNA.
Example, hsa-miR-146b-3p (MIMAT0004766):

    TargetScan (v22 era)  GCCCTGT
    miRBase R23           CCCTGTG

The same window slid one nucleotide along the sequence. Because the seed
is defined as positions 2-8, trimming or extending the 5' end renumbers
every position.

## Bridge result

Joining TargetScan to R23 by miRBase accession:

- 2502 / 2606 (96.0%) resolve to a current R23 miRNA
- of those, 238 have a seed that has changed since v22
  (234 changed between R22 and R23; 4 are TargetScan curation)
- 104 accessions no longer exist in R23; 31 of them can still be
  recovered through their seed family, 73 (2.8%) cannot

## Consequence for the tool

Rows whose seed changed carry `seed_matches_current = 0`. TargetScan's
prediction for those was computed against a different seed than the one
our own seed analyser uses, so the two tools are answering slightly
different questions. The results table marks them rather than hiding
the discrepancy.

## Gene identifier bridge (TargetScan Gene_info -> MANE)

TargetScan Gene_info lists 28352 human transcripts across 19474 genes,
using versioned Ensembl identifiers (ENST/ENSG). Version suffixes are
stripped before joining.

Join key comparison (distinct TargetScan entries finding a MANE match):

| key | matches |
|---|---|
| Ensembl transcript | 12875 |
| Ensembl gene | 18187 |
| gene symbol | 17212 |

Resolver cascade, Ensembl gene -> symbol -> alias:

- 18187 on Ensembl gene
- 285 more on gene symbol
- 121 more on gene alias
- 881 unresolved
- 18593 / 19474 (95.5%) resolved

## Transcript choice

TargetScan predicts on its own representative transcript per gene,
chosen by 3P-seq support. For resolved genes:

- 11372 (61.2%) TargetScan's representative is the MANE transcript
- 7189 (38.7%) it is a different transcript
- 32 no representative flagged

Consequence: TargetScan results are joined and displayed at gene level,
never transcript level, and no TargetScan site position is shown. For
the 38.7% the underlying 3' UTR sequence differs from the one our own
tools scan, so positions would not be comparable.

## Load result (2026-09-07)

Human rows in Summary_Counts.all_predictions: 7765065

| outcome | rows |
|---|---|
| loaded | 7501712 |
| dropped, gene not in MANE | 226824 |
| dropped, duplicate Ensembl gene for one Entrez | 36529 |

Every input row is accounted for; the three figures sum to 7765065.

Tables:

- targetscan_mirnas 2580 rows (26 TargetScan 5' isoform entries skipped:
  they carry no miRBase accession, so they cannot be bridged)
- targetscan_genes 18357 rows, 11320 (61.7%) on the MANE transcript
- targetscan 7501712 rows, 2064 distinct seeds, 107790 flagged in_default

110 Entrez ids received more than one Ensembl gene id. Where that happened
the Ensembl gene whose representative transcript is the MANE transcript was
kept; ties broken by sorted Ensembl id, so the load is reproducible.

## End-to-end check

hsa-miR-21-5p -> MIMAT0000076 -> seed AGCTTAT -> 2598 target genes.
PDCD4: 1 conserved site, context++ -0.503, PCT 0.846, in TargetScan's
default set. Our own seed analyser independently finds an 8mer site in
the PDCD4 3' UTR at position 1806.

hsa-miR-107 (a retired name) resolves through the alias bridge to
MIMAT0000104 and returns 4338 target genes, DICER1 first.
