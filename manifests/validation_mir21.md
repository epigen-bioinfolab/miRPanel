# Validation — hsa-miR-21-5p against published targets

Nine genes, four tools, one job. Eight are miR-21 targets with published
functional evidence; GAPDH is a negative control. Run through the web
interface, so this also exercises the API and the frontend.

Job: 53 records — seed 13, rnahybrid 26, targetscan 6, mirtarbase 8.

## Result

| Gene | Seed | Region | ΔG | context++ | P_CT | Strong exp. | No effect |
|---|---|---|---|---|---|---|---|
| TIMP3 | 8mer ×2 | 3′UTR | −22.8 | **−0.675** | **0.87** | 15 | 0 |
| PDCD4 | 8mer | 3′UTR | −18.5 | −0.503 | 0.85 | 59 | 6 |
| SPRY2 | 8mer | 3′UTR | −19.4 | −0.385 | 0.69 | 6 | 1 |
| RECK | 8mer | 3′UTR | −24.9 | −0.378 | 0.63 | 15 | 2 |
| BCL2 | 7mer-m8 | **CDS** | −19.4 | −0.117 | 0.27 | 9 | 3 |
| PTEN | 7mer-A1 | 3′UTR | −20.2 | **−0.012** | **none** | **91** | **23** |
| TPM1 | 7mer-A1 | 3′UTR | −22.1 | **none** | — | 6 | 1 |
| MARCKS | **none** | — | −21.1 | none | — | 2 | 2 |
| GAPDH | none | — | −20.6 | not covered | not covered | **not reported** | — |

## Recall on eight published targets

| Tool | Recovered | Note |
|---|---|---|
| miRTarBase | 8 / 8 | and GAPDH correctly absent |
| seed analyser (ours) | 7 / 8 | only MARCKS has no canonical site |
| TargetScan | 6 / 8 | misses TPM1 and MARCKS |
| RNAhybrid | 9 / 9 | including the negative control — sensitive, not selective |

miRTarBase recovering 8/8 is a check on the loader and the name
reconciliation (91,657 aliases, historical miRBase releases), not on the
prediction: miRTarBase *is* the reference here.

## Three findings

**1. Prediction strength does not track experimental support.**

    by context++     TIMP3 > PDCD4 > SPRY2 > RECK > BCL2 > PTEN
    by experiments   PTEN  > PDCD4 > RECK  > TIMP3 > BCL2 > SPRY2

PTEN is last by prediction and first by evidence: 91 strong experiments
across 20 papers, context++ −0.012, and no conserved site. A single
combined score would have averaged the most-validated target in the set
down to nothing. This is the concrete case for per-tool columns.

Caveat, stated plainly: experiment counts measure how much a pair has been
studied, and PTEN is a famous gene. The disagreement is real; the reason
for it is not only biology.

**2. TargetScan misses TPM1 because of transcript choice, not biology.**

TPM1 is present in `targetscan_genes` but has **zero** rows for the miR-21
seed. We load *all* TargetScan predictions, not just conserved ones, so any
7mer-A1 in the 3′UTR TargetScan scored would have produced a row. Our
scanner finds a 7mer-A1 at 1,126–1,132 on the MANE Select transcript
(NM_001018005.2), and the pair is published (Zhu et al., 2007).

The site therefore lies outside the 3′UTR TargetScan chose. TPM1 is heavily
spliced. This is the 38.7% transcript-mismatch measured in Phase 4, landing
on a validated target — and a direct argument for anchoring on MANE Select.

**3. BCL2's strongest canonical site is in the CDS.**

7mer-m8 at 944–950, coding sequence. TargetScan reads 3′UTRs only, so it
scores BCL2 on a different, weaker site (−0.117, P_CT 0.27) while the pair
has 9 strong experiments. A 3′UTR-only tool cannot see this class of site,
which is the argument for the ML model covering all three regions.

## What this is not

- **Nine hand-picked positives are not a benchmark.** There is no random
  negative set, so no precision, no false-positive rate, no ROC.
- **No independent replication of miRTarBase.** It is our evidence source.
- A real benchmark needs: a defined miRNA set, all miRTarBase strong pairs
  as positives, matched random genes as negatives, and recall/precision per
  tool. Planned as its own phase.

## Reproduce

Web interface, or:

    python scripts/run_job.py hsa-miR-21-5p PDCD4 PTEN RECK TPM1 SPRY2 \
        TIMP3 BCL2 MARCKS GAPDH --tools seed,targetscan,mirtarbase,rnahybrid
