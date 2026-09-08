# Phase 5: orchestrator design

## A job is one miRNA

One job = one miRNA against one target set. Several miRNAs become several
jobs sharing a batch_id. A failure then costs one miRNA rather than the
whole submission, retries are cheap, and progress is reportable per miRNA.

## The tool contract

Every tool module defines:

    META                  name, version, kind, score_type, better,
                          gives_position, needs_sequence, slow
    covers(con, entrez)   can this tool say anything about this gene
    run(con, mirna, targets, opts, progress)
                          -> {records, provenance, warnings}

Loading a tool validates META, so a tool that omits `better` cannot be
registered. That matters because `better` tells the results page which
direction is stronger: context++ and MFE are better when lower, an ML
probability when higher. Without it a column would silently sort backwards.

`kind` is prediction or evidence. miRTarBase is evidence and is never
presented as a predictor.

Every position is 1-based on the MANE transcript. A tool working on a
sub-sequence converts inside its own wrapper.

## Three empty-cell states

- not run      : no row in tool_runs for that tool
- not covered  : the tool ran but covers() is false for that gene
- no site      : the tool ran, covers the gene, produced no record

A blank cell must never be read as "no target".

## Target set: MANE Select only

all_targets() returns the 19363 MANE Select transcripts, not the 19437
that include MANE Plus Clinical. Each of those 74 belongs to a gene that
already has a Select transcript, so including them would list 74 genes
twice with different coordinates.

Verified: hsa-miR-21-5p gives 4365 sites of 7mer or better across MANE
Select, and the 74 Plus Clinical transcripts contribute exactly 28 more,
reproducing the 4393 measured before the orchestrator existed.

## Failure handling

A tool that raises is recorded in tool_runs with status 'failed' and the
exception text; the other tools still run and their results are stored.
run_job clears its own previous results first, so re-running a job is safe
and idempotent.

## Deferred to Phase 7 (display, no data loss)

- miRTarBase score 0.0 means "no strong evidence, weak evidence exists".
  It must render as "Reported (CLIP)", never as a score of zero. The value
  is already in extra.status. A per-tool `label` field would let the
  frontend avoid parsing tool-specific JSON; results are regenerable, so
  adding it later costs one re-run.
- TargetScan aggregate_pct 0.000 means no conservation evidence and must
  render as "n/a", never as a probability of zero.

## Transcriptome-wide run, hsa-miR-21-5p (2026-09-08)

19363 MANE Select transcripts, four tools, 58954 results.

| tool | rows | genes reached | seconds |
|---|---|---|---|
| seed | 10254 | 6673 | 0.84 |
| targetscan | 2598 | 2598 | 0.03 |
| mirtarbase | 1068 | 1068 | 0.01 |
| rnahybrid | 45034 | 17671 | 803.6 |

Total wall clock 13m24s. RNAhybrid is 99.9% of it, which is why it is
marked slow and left out of the default tool set. The three fast tools
together complete a transcriptome-wide job in about one second.

## Position verification

All 45034 RNAhybrid records were checked by rebuilding the target strand
from the alignment rows and comparing it against
transcript[pos_start-1 : pos_end]. Zero mismatches. 50 positions carry an
N placeholder in RNAhybrid's alignment output, which matches any base.

## RNAhybrid energy threshold, chosen from the distribution

Genes reached at each MFE cutoff, hsa-miR-21-5p:

| cutoff kcal/mol | genes | share of transcriptome |
|---|---|---|
| -15 | 17643 | 91% |
| -20 | 11741 | 61% |
| -25 | 1696 | 8.8% |
| -30 | 65 | 0.3% |

At -15 RNAhybrid reports a site in 91% of human genes, which is not a
prediction. low_confidence is therefore set at -25, where the gene count
(1696) is comparable to TargetScan (2598) and the seed analyser (6673).
Weaker sites are still stored and still shown when asked for.

Caveat: a fixed energy threshold favours long transcripts, which have more
opportunities to contain a low-energy duplex. This is the same composition
confound measured for seed matches in Phase 4, and it has not yet been
quantified for MFE.
