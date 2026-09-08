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
