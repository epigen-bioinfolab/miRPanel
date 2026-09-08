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
