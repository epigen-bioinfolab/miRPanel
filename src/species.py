"""The organisms this tool can analyse.

One dict, read by everything else. The key is the string stored in
`transcripts.species` and `genes.species`; 'human' is already in the
database from the MANE load, so the other four follow the same style
(lowercase common name, not a miRBase prefix).

Nothing here is computed at import time and nothing touches the
database, so this module is safe to import from anywhere.
"""

ENSEMBL_RELEASE = "116"

# Ensembl 116 (June 2026) is the LAST release on the classic FTP
# platform; everything after it moves to the new Ensembl site. Pinning
# to 116 means the links handed to users keep resolving to the same
# bytes. Do not change this to 'current'.
_FTP = "https://ftp.ensembl.org/pub/release-" + ENSEMBL_RELEASE

SPECIES = {
    "human": {
        "common":    "Human",
        "latin":     "Homo sapiens",
        "taxid":     "9606",
        "mirbase":   "hsa",
        "source":    "MANE",          # loaded, not uploaded
        "assembly":  "GRCh38",
        "ensembl":   "homo_sapiens",
        "scanmir":   "shipped",       # scanMiRData has hsa models
        "orgdb":     "org.Hs.eg.db",
        "kegg":      "hsa",
        "tools":     ("seed", "rnahybrid", "scanmir", "targetscan",
                      "mirtarbase"),
    },
    "mouse": {
        "common":    "Mouse",
        "latin":     "Mus musculus",
        "taxid":     "10090",
        "mirbase":   "mmu",
        "source":    "Ensembl",
        "assembly":  "GRCm39",        # confirmed for Ensembl 116
        "ensembl":   "mus_musculus",
        "scanmir":   "shipped",
        "orgdb":     "org.Mm.eg.db",
        "kegg":      "mmu",
        # TargetScanMouse 8.0 and miRTarBase mouse rows both exist and
        # are downloadable, but neither is LOADED yet. This tuple says
        # what the tool can actually do today, not what is obtainable -
        # listing a tool whose table holds only human data would run
        # human predictions against mouse genes and report them as
        # mouse results. Add them here when their loaders run.
        "tools":     ("seed", "rnahybrid", "scanmir"),
    },
    "rat": {
        "common":    "Rat",
        "latin":     "Rattus norvegicus",
        "taxid":     "10116",
        "mirbase":   "rno",
        "source":    "Ensembl",
        # GRCr8, not the older mRatBN7.2 - Ensembl moved to the new rat
        # assembly, and the old name 404s on release 116.
        "assembly":  "GRCr8",
        "ensembl":   "rattus_norvegicus",
        "scanmir":   "shipped",
        "orgdb":     "org.Rn.eg.db",
        "kegg":      "rno",
        # TargetScan has no standalone rat release; rat rows can be
        # pulled out of the TargetScanMouse 46-way files by species id
        # 10116. miRTarBase does carry rat records. Neither is loaded,
        # so neither is declared - see NOT_LOADED below.
        "tools":     ("seed", "rnahybrid", "scanmir"),
    },
    "rabbit": {
        "common":    "Rabbit",
        "latin":     "Oryctolagus cuniculus",
        "taxid":     "9986",
        "mirbase":   "ocu",
        "source":    "Ensembl",
        # OryCun2.0 is a 2009 6.5x draft with >80,000 unresolved gaps.
        # 3'UTR annotation is thin. This is a stated limitation, not a
        # bug in the loader.
        "assembly":  "OryCun2.0",     # confirmed for Ensembl 116
        "ensembl":   "oryctolagus_cuniculus",
        "scanmir":   "none",          # see SCANMIR_SPECIES below
        "orgdb":     None,            # no rabbit OrgDb exists -> no GO
        "kegg":      "ocu",
        "tools":     ("seed", "rnahybrid"),
    },
    "fly": {
        "common":    "Drosophila",
        "latin":     "Drosophila melanogaster",
        "taxid":     "7227",
        "mirbase":   "dme",
        "source":    "Ensembl",
        "assembly":  "BDGP6.54",
        # Drosophila is annotated by Ensembl Genomes, which numbers its
        # releases separately: Ensembl Genomes 63 is the counterpart to
        # Ensembl 116, and the GTF filename carries 63. The cDNA FASTA
        # has no release number in its name, so only the GTF is affected
        # - which is exactly how this was missed until the links were
        # actually requested.
        "gtf_release": "63",
        "ensembl":   "drosophila_melanogaster",
        "scanmir":   "none",          # see SCANMIR_SPECIES below
        "orgdb":     "org.Dm.eg.db",
        "kegg":      "dme",
        # TargetScanFly is release 7.2, not 8.0 - a real version
        # mismatch that provenance must report honestly if loaded.
        "tools":     ("seed", "rnahybrid"),
    },
}

DEFAULT = "human"

#: Species whose transcripts are loaded at install time rather than
#: uploaded by the user.
PRELOADED = ("human",)


def get(key):
    """The record for one species, or ValueError naming the valid keys."""
    try:
        return SPECIES[key]
    except KeyError:
        raise ValueError("unknown species %r (expected one of: %s)"
                         % (key, ", ".join(sorted(SPECIES))))


def fasta_url(key):
    """Download URL for the spliced cDNA FASTA.

    cdna.all is the right file: it is the spliced transcript, UTRs
    included. 'cds' would drop both UTRs and 'ncrna' is a different
    set entirely - users pick the wrong one constantly, which is why
    the page shows the full filename and not just the directory.
    """
    s = get(key)
    return "%s/fasta/%s/cdna/%s.%s.cdna.all.fa.gz" % (
        _FTP, s["ensembl"], s["latin"].replace(" ", "_"), s["assembly"])


def gtf_url(key):
    """Download URL for the matching GTF.

    Needed for three things a bare FASTA cannot give: CDS bounds (so
    scanMiR's ORF penalty applies at all), which transcript is
    canonical, and gene symbols.
    """
    s = get(key)
    return "%s/gtf/%s/%s.%s.%s.gtf.gz" % (
        _FTP, s["ensembl"], s["latin"].replace(" ", "_"), s["assembly"],
        s.get("gtf_release", ENSEMBL_RELEASE))


def files(key):
    """(fasta_filename, gtf_filename) - what the user should end up with."""
    return (fasta_url(key).rsplit("/", 1)[1], gtf_url(key).rsplit("/", 1)[1])


def supports(key, tool):
    """Is `tool` meaningful for this species?

    A tool that is not supported is dropped from the job with a
    recorded reason, the same way orchestrator records a failing tool
    rather than killing the run. It is never silently returned empty -
    an empty column and an unavailable column mean different things.
    """
    return tool in get(key)["tools"]


#: Tools whose dataset EXISTS for a species but has not been loaded
#: into this installation yet. Kept apart from "no such dataset"
#: because the two need different sentences on screen: one is a
#: permanent fact about the data, the other is a to-do here. Saying
#: the wrong one would be worse than saying nothing.
NOT_LOADED = {
    "mouse": {
        "targetscan": "TargetScanMouse 8.0 exists but is not loaded "
                      "in this installation yet.",
        "mirtarbase": "miRTarBase has mouse records, but they are not "
                      "loaded in this installation yet.",
    },
    "rat": {
        "targetscan": "TargetScan has no standalone rat release; rat "
                      "rows must be extracted from the mouse 46-way "
                      "files, which has not been done yet.",
        "mirtarbase": "miRTarBase has rat records, but they are not "
                      "loaded in this installation yet.",
    },
    "fly": {
        "targetscan": "TargetScanFly 7.2 exists but is not loaded in "
                      "this installation yet.",
        "mirtarbase": "miRTarBase has fly records, but they are not "
                      "loaded in this installation yet.",
    },
}


#: The only species scanMiR can assess. scanMiRData ships KdModel
#: collections for these three and no others.
#:
#: These cannot be extended. A KdModel is a table of 12-mer dissociation
#: constants, and scanMiR's getKdModel() takes that table as its first,
#: required argument - it does not derive one from a sequence. The table
#: comes out of the convolutional network of McGeary et al. (2019),
#: which is a separate Python program and not part of the R package. So
#: a rabbit or fly miRNA has no model and cannot be given one here, and
#: scanMiR reports N.A. for those species rather than a number borrowed
#: from another organism's model.
SCANMIR_SPECIES = ("hsa", "mmu", "rno")


def unsupported_reason(key, tool):
    """One plain sentence for the UI, or None if the tool is fine."""
    if supports(key, tool):
        return None
    s = get(key)
    if tool == "scanmir" and s["mirbase"] not in SCANMIR_SPECIES:
        return ("scanMiR has no affinity models for %s, and they cannot be "
                "built without the published CNN that generated them."
                % s["common"].lower())
    pending = NOT_LOADED.get(key, {}).get(tool)
    if pending:
        return pending
    if tool == "targetscan":
        return ("TargetScan publishes no prediction set for %s."
                % s["common"].lower())
    if tool == "mirtarbase":
        return ("miRTarBase holds no experimental evidence for %s."
                % s["common"].lower())
    return "%s is not available for %s." % (tool, s["common"].lower())


def source_name(key):
    """The data_sources.name for this species' transcript set.

    data_sources.name is a PRIMARY KEY, so every species needs its own
    row name. Human keeps the existing bare 'MANE' row untouched.
    """
    if key == "human":
        return "MANE"
    return "Ensembl-" + key


def prefix_ok(key, mirna_name):
    """Does a miRNA name belong to this species?

    Used to reject 'hsa-miR-21-5p' against a rabbit transcriptome
    before a job is queued, rather than returning zero rows and
    looking broken. A name with no recognised prefix passes - the
    user may have typed an accession or a raw sequence.
    """
    want = get(key)["mirbase"]
    head = mirna_name.strip().lower()[:4]
    if len(head) < 4 or head[3] != "-":
        return True
    return head[:3] == want
