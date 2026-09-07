"""Reader for the MANE RefSeq GenBank flatfile."""
import gzip, re

GBFF = "data/raw/MANE.GRCh38.v1.5.refseq_rna.gbff.gz"
LOC = re.compile(r"^<?(\d+)\.\.>?(\d+)$")


def raw_records(path=GBFF):
    """Yield (version, length, features_text, sequence), one record at a time."""
    ver = length = None
    feat, seq, where = [], [], None
    with gzip.open(path, "rt") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("LOCUS"):
                length = int(line.split()[2])
                ver, feat, seq, where = None, [], [], None
            elif line.startswith("VERSION"):
                ver = line.split()[1]
            elif line.startswith("FEATURES"):
                where = "f"
            elif line.startswith("ORIGIN"):
                where = "s"
            elif line.startswith("//"):
                yield ver, length, "\n".join(feat), "".join(seq).upper()
            elif where == "f":
                feat.append(line)
            elif where == "s":
                seq.append("".join(c for c in line if c.isalpha()))


def _q(text, name):
    m = re.search('/%s="([^"]+)"' % name, text)
    return m.group(1) if m else ""


def transcripts(path=GBFF):
    """Yield one dict per transcript."""
    for ver, length, feat, seq in raw_records(path):
        flat = re.sub(r"\n {21}", " ", feat)
        g = re.search(r'/db_xref="GeneID:(\d+)"', flat)
        rec = {"refseq": ver,
               "refseq_base": ver.split(".")[0] if ver else None,
               "length": length,
               "symbol": _q(flat, "gene"),
               "synonyms": _q(flat, "gene_synonym"),
               "entrez": g.group(1) if g else None,
               "cds_start": None, "cds_end": None, "cds_raw": None,
               "sequence": seq}
        m = re.search(r"^     CDS\s+(\S+)", feat, re.M)
        if m:
            rec["cds_raw"] = m.group(1)
            loc = LOC.match(m.group(1))
            if loc:
                rec["cds_start"] = int(loc.group(1))
                rec["cds_end"] = int(loc.group(2))
        yield rec


def regions(rec):
    """Return [(name, start, end)], 1-based inclusive. Empty regions are omitted."""
    L, s, e = rec["length"], rec["cds_start"], rec["cds_end"]
    if s is None:
        return [("ncRNA", 1, L)]
    out = []
    if s > 1:
        out.append(("5UTR", 1, s - 1))
    out.append(("CDS", s, e))
    if e < L:
        out.append(("3UTR", e + 1, L))
    return out
