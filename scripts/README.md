# scripts/

Most of what is in here was written while building miRPanel and is kept
because it documents how a decision was reached. Only a few are meant to be
run by a user.

## Run these

| Script | What it does |
|---|---|
| `check_env.py` | Checks Python, R, RNAhybrid, the R packages and the database. Run it first, and whenever something fails for no obvious reason. |
| `prune_jobs.py` | Deletes old searches and reclaims the disk they hold. Reference data is never touched. |

## Building the database

Run once, in this order. Each one downloads its source and loads it.

| Script | Loads |
|---|---|
| `load_mane.py` | Human transcripts, MANE Select v1.5 |
| `load_mirbase.py` | miRNAs, miRBase Release 23 |
| `load_mirbase_history.py` | Earlier miRBase releases, for name resolution |
| `load_targetscan.py` | TargetScan v8.0, human |
| `load_mirtarbase.py` | miRTarBase 10.0, human |
| `load_ensembl.py` | Mouse, rat, rabbit and fly transcripts |
| `load_targetscan_mouse.py` | TargetScan, mouse |
| `load_mirtarbase_species.py` | miRTarBase for mouse, rat and fly |
| `register_scanmir.py` | Registers the scanMiR models that ship with scanMiRData |

## Run by the tool itself, not by hand

| Script | Called by |
|---|---|
| `worker.py` | `worker.sh`; runs queued searches |
| `build_page.py` | regenerates `web/index.html` after a front-end change |
| `scanmir_run.R` | the scanMiR tool |
| `kd_to_model.R` | model generation for organisms without a shipped model |

`web/index.html` is generated. Edit `build_page.py` and rerun it; never edit
the HTML directly.

## Tests

`test_api.py`, `test_geneset.py` and `test_resolve.py`.

## Everything else

Development scripts, kept for the record rather than for use:

- `spike_*.py` — exploratory runs that established how a tool behaves
- `check_*.py` — one-off data checks made while loading each source
- `benchmark_*.py` — a benchmark harness, written but not yet run
- `km_*.R`, `scanmir_*.R` — scanMiR model inspection and timing
- `targetscan_*.py`, `inspect_*.py`, `compare_mirbase.py` and the rest —
  measurements behind decisions recorded in `manifests/`

They are not needed to install or run miRPanel, and several expect data files
or conditions that no longer exist.
