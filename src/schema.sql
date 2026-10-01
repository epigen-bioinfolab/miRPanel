-- Provenance: one row per downloaded file.
CREATE TABLE IF NOT EXISTS data_sources (
    name          TEXT PRIMARY KEY,
    version       TEXT NOT NULL,
    url           TEXT,
    downloaded_on TEXT NOT NULL,
    bytes         INTEGER,
    sha256        TEXT,
    notes         TEXT
);

-- One row per gene.
CREATE TABLE IF NOT EXISTS genes (
    entrez        TEXT PRIMARY KEY,
    symbol        TEXT NOT NULL,
    ensembl_gene  TEXT,
    ensembl_base  TEXT,
    hgnc          TEXT,
    description   TEXT,
    species       TEXT NOT NULL
);

-- One row per transcript, including its sequence.
CREATE TABLE IF NOT EXISTS transcripts (
    refseq        TEXT PRIMARY KEY,
    refseq_base   TEXT NOT NULL,
    ensembl       TEXT,
    ensembl_base  TEXT,
    entrez        TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    mane_status   TEXT,
    length        INTEGER NOT NULL,
    cds_start     INTEGER,
    cds_end       INTEGER,
    biotype       TEXT NOT NULL,
    species       TEXT NOT NULL,
    canonical     INTEGER NOT NULL DEFAULT 0,
    sequence      TEXT NOT NULL
);

-- One row per region of a transcript: 5UTR, CDS, 3UTR or ncRNA.
CREATE TABLE IF NOT EXISTS regions (
    refseq        TEXT NOT NULL,
    region        TEXT NOT NULL,
    start_pos     INTEGER NOT NULL,
    end_pos       INTEGER NOT NULL,
    length        INTEGER NOT NULL,
    PRIMARY KEY (refseq, region)
);

-- Old and alternative gene names, so H731 finds PDCD4.
CREATE TABLE IF NOT EXISTS gene_aliases (
    alias         TEXT NOT NULL,
    entrez        TEXT NOT NULL,
    source        TEXT NOT NULL,
    PRIMARY KEY (alias, entrez)
);

-- Indexes: every column the identifier resolver will search.
CREATE INDEX IF NOT EXISTS ix_genes_symbol ON genes(symbol);
CREATE INDEX IF NOT EXISTS ix_genes_ens    ON genes(ensembl_base);
CREATE INDEX IF NOT EXISTS ix_tx_base      ON transcripts(refseq_base);
CREATE INDEX IF NOT EXISTS ix_tx_ens       ON transcripts(ensembl_base);
CREATE INDEX IF NOT EXISTS ix_tx_entrez    ON transcripts(entrez);
CREATE INDEX IF NOT EXISTS ix_tx_symbol    ON transcripts(symbol);
CREATE INDEX IF NOT EXISTS ix_tx_species   ON transcripts(species, canonical);
CREATE INDEX IF NOT EXISTS ix_alias        ON gene_aliases(alias);

-- One row per mature miRNA, keyed by miRBase accession (stable across releases).
CREATE TABLE IF NOT EXISTS mirnas (
    accession     TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    sequence      TEXT NOT NULL,
    seed          TEXT NOT NULL,
    species       TEXT NOT NULL,
    release       TEXT NOT NULL,
    seed_changed  INTEGER NOT NULL DEFAULT 0
);

-- Every name a miRNA has ever had, pointing at its accession.
CREATE TABLE IF NOT EXISTS mirna_aliases (
    alias         TEXT NOT NULL,
    accession     TEXT NOT NULL,
    source        TEXT NOT NULL,
    PRIMARY KEY (alias, accession)
);

CREATE INDEX IF NOT EXISTS ix_mir_name    ON mirnas(name);
CREATE INDEX IF NOT EXISTS ix_mir_seed    ON mirnas(seed);
CREATE INDEX IF NOT EXISTS ix_mir_species ON mirnas(species);
CREATE INDEX IF NOT EXISTS ix_mir_alias   ON mirna_aliases(alias);

CREATE TABLE IF NOT EXISTS targetscan_mirnas (
    accession    TEXT PRIMARY KEY,
    ts_name      TEXT NOT NULL,
    family       TEXT NOT NULL,
    seed         TEXT NOT NULL,
    conservation INTEGER NOT NULL,
    species      TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_tsmir_seed ON targetscan_mirnas(seed);

CREATE TABLE IF NOT EXISTS targetscan_genes (
    entrez        TEXT PRIMARY KEY,
    ts_transcript TEXT NOT NULL,
    ensembl_base  TEXT NOT NULL,
    ts_symbol     TEXT NOT NULL,
    is_mane       INTEGER NOT NULL);

CREATE INDEX IF NOT EXISTS idx_tsgene_tx ON targetscan_genes(ts_transcript);

CREATE TABLE IF NOT EXISTS targetscan (
    seed                  TEXT NOT NULL,
    entrez                TEXT NOT NULL,
    sites_conserved       INTEGER NOT NULL,
    sites_8mer_c          INTEGER NOT NULL,
    sites_7mer_m8_c       INTEGER NOT NULL,
    sites_7mer_a1_c       INTEGER NOT NULL,
    sites_nonconserved    INTEGER NOT NULL,
    sites_8mer_n          INTEGER NOT NULL,
    sites_7mer_m8_n       INTEGER NOT NULL,
    sites_7mer_a1_n       INTEGER NOT NULL,
    sites_6mer            INTEGER NOT NULL,
    context_score         REAL,
    cumulative_score      REAL,
    aggregate_pct         REAL,
    occupancy_low         REAL,
    occupancy_high        REAL,
    occupancy_transfected REAL,
    in_default            INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (seed, entrez));

CREATE INDEX IF NOT EXISTS idx_targetscan_entrez ON targetscan(entrez);

CREATE TABLE IF NOT EXISTS mirtarbase_evidence (
    row_id      INTEGER PRIMARY KEY,
    mtb_id      TEXT NOT NULL,
    mirna_name  TEXT NOT NULL,
    accession   TEXT,
    entrez      TEXT,
    symbol      TEXT NOT NULL,
    functional  INTEGER NOT NULL,
    strong      INTEGER NOT NULL,
    experiments TEXT NOT NULL,
    pmid        TEXT,
    species     TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_mtbev_pair ON mirtarbase_evidence(accession, entrez);
CREATE INDEX IF NOT EXISTS idx_mtbev_gene ON mirtarbase_evidence(entrez);
CREATE INDEX IF NOT EXISTS idx_mtbev_id   ON mirtarbase_evidence(mtb_id);

CREATE TABLE IF NOT EXISTS mirtarbase_sites (
    mtb_id      TEXT NOT NULL,
    accession   TEXT,
    entrez      TEXT,
    target_site TEXT NOT NULL,
    functional  INTEGER NOT NULL,
    strong      INTEGER NOT NULL,
    pmid        TEXT);

CREATE INDEX IF NOT EXISTS idx_mtbsite_pair ON mirtarbase_sites(accession, entrez);

CREATE TABLE IF NOT EXISTS mirtarbase (
    accession        TEXT NOT NULL,
    entrez           TEXT NOT NULL,
    n_strong_func    INTEGER NOT NULL,
    n_weak_func      INTEGER NOT NULL,
    n_strong_nonfunc INTEGER NOT NULL,
    n_weak_nonfunc   INTEGER NOT NULL,
    n_sites          INTEGER NOT NULL,
    pmids            TEXT,
    PRIMARY KEY (accession, entrez));

CREATE INDEX IF NOT EXISTS idx_mtb_gene ON mirtarbase(entrez);

CREATE TABLE IF NOT EXISTS jobs (
    job_id      TEXT PRIMARY KEY,
    batch_id    TEXT,
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT,
    status      TEXT NOT NULL,
    params      TEXT NOT NULL,
    n_results   INTEGER NOT NULL DEFAULT 0,
    error       TEXT);

CREATE INDEX IF NOT EXISTS idx_jobs_batch ON jobs(batch_id);

CREATE TABLE IF NOT EXISTS tool_runs (
    job_id     TEXT NOT NULL,
    tool       TEXT NOT NULL,
    status     TEXT NOT NULL,
    n_results  INTEGER NOT NULL DEFAULT 0,
    seconds    REAL,
    provenance TEXT,
    message    TEXT,
    PRIMARY KEY (job_id, tool));

CREATE TABLE IF NOT EXISTS results (
    job_id         TEXT NOT NULL,
    mirna_acc      TEXT NOT NULL,
    mirna_name     TEXT NOT NULL,
    entrez         TEXT NOT NULL,
    symbol         TEXT NOT NULL,
    refseq         TEXT,
    region         TEXT,
    tool           TEXT NOT NULL,
    site_type      TEXT,
    pos_start      INTEGER,
    pos_end        INTEGER,
    score          REAL,
    score_type     TEXT,
    low_confidence INTEGER NOT NULL DEFAULT 0,
    extra          TEXT);

CREATE INDEX IF NOT EXISTS idx_results_job  ON results(job_id);
CREATE INDEX IF NOT EXISTS idx_results_pair ON results(job_id, entrez);
CREATE INDEX IF NOT EXISTS idx_results_tool ON results(job_id, tool);

-- ---------------------------------------------------------------------------
-- Phase 8: pathway analysis. Same shape as jobs/results: one row describing
-- the analysis, many rows of output.
--
-- Nothing here is ever deleted when a job is re-run. Each run stores the gene
-- ids it actually tested, so it stays valid for those genes forever;
-- job_finished_at records what the job looked like at the time, which is how
-- the interface tells a current run from a historical one.

CREATE TABLE IF NOT EXISTS enrichment_runs (
    run_id            TEXT PRIMARY KEY,
    job_id            TEXT NOT NULL,
    job_finished_at   TEXT,            -- jobs.finished_at when this was run
    created_at        TEXT NOT NULL,
    started_at        TEXT,
    finished_at       TEXT,
    status            TEXT NOT NULL,   -- queued | running | done | failed
    error             TEXT,

    -- what was selected
    spec_json         TEXT NOT NULL,
    spec_hash         TEXT NOT NULL,
    rule_sentence     TEXT NOT NULL,
    gene_ids          TEXT NOT NULL,   -- the Entrez ids actually tested
    n_genes           INTEGER NOT NULL,
    n_genes_annotated INTEGER,         -- how many org.Hs.eg.db recognised

    -- what it was tested against
    background             TEXT NOT NULL,   -- 'mane_select'
    background_source      TEXT NOT NULL,   -- data_sources.name
    background_version     TEXT NOT NULL,   -- data_sources.version
    n_background           INTEGER NOT NULL,
    n_background_annotated INTEGER,

    -- how the test was done
    p_adjust_method   TEXT NOT NULL,
    p_cutoff          REAL NOT NULL,
    q_cutoff          REAL,
    ontologies        TEXT NOT NULL,

    -- what did the computing
    r_version               TEXT,
    clusterprofiler_version TEXT,
    orgdb_version           TEXT,
    kegg_ok                 INTEGER,
    kegg_fetched_at         TEXT,

    n_terms           INTEGER,
    seconds           REAL
);

CREATE TABLE IF NOT EXISTS enrichment_terms (
    run_id       TEXT NOT NULL,
    source       TEXT NOT NULL,        -- GO:BP | GO:MF | GO:CC | KEGG
    term_id      TEXT NOT NULL,
    description  TEXT NOT NULL,

    -- the four numbers of the hypergeometric test, so every p-value here can
    -- be recomputed by anyone, in any language, without rerunning R
    k_in_term_and_list       INTEGER NOT NULL,
    n_in_list                INTEGER NOT NULL,
    k_in_term_and_background INTEGER NOT NULL,
    n_in_background          INTEGER NOT NULL,

    p_value      REAL NOT NULL,
    p_adjust     REAL NOT NULL,
    q_value      REAL,
    genes        TEXT NOT NULL,        -- symbols driving the term
    PRIMARY KEY (run_id, source, term_id)
);

CREATE INDEX IF NOT EXISTS idx_enr_terms_run ON enrichment_terms(run_id, p_adjust);
CREATE INDEX IF NOT EXISTS idx_enr_runs_job  ON enrichment_runs(job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_enr_runs_hash ON enrichment_runs(job_id, spec_hash);

-- One standing HTML report per row. The rendered document is stored rather
-- than regenerated on demand, for the same reason enrichment runs are kept:
-- a report is a scientific artefact with a date on it, and re-rendering it
-- later against a re-run job would quietly change what it says. Nothing here
-- is ever deleted.
CREATE TABLE IF NOT EXISTS reports (
    report_id       TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    job_finished_at TEXT,              -- jobs.finished_at when this was asked for
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    finished_at     TEXT,
    status          TEXT NOT NULL,     -- queued | running | done | failed
    error           TEXT,

    spec_json       TEXT NOT NULL,     -- sort and top_n, fixed at request time
    enrichment_run  TEXT,              -- the run included, chosen at request time
    n_genes         INTEGER,           -- how many genes the report actually shows
    html            TEXT,              -- the rendered document
    bytes           INTEGER,
    seconds         REAL
);

CREATE INDEX IF NOT EXISTS idx_reports_job    ON reports(job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at);
