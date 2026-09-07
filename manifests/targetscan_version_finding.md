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
