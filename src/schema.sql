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
