"""Load one species' canonical transcripts from an Ensembl cDNA FASTA + GTF pair.

    python3 scripts/load_ensembl.py mouse \
        --fasta data/raw/Mus_musculus.GRCm39.cdna.all.fa.gz \
        --gtf   data/raw/Mus_musculus.GRCm39.116.gtf.gz \
        --check Pten

Run it with --check first. It parses everything, prints one gene's
region bounds, and writes nothing. Only --load touches the database.

WHY THIS FILE EXISTS
--------------------
A cDNA FASTA alone is not enough. It has no CDS boundary, so scanMiR
would treat every transcript as pure 3'UTR and the ORF penalty would
never apply - the same failure measured on the human side (117,235
sites instead of 88,828). The numbers still look plausible. They are
just wrong. The GTF carries the CDS, but in GENOMIC coordinates, and
every stored position in this tool is 1-based on the TRANSCRIPT. The
conversion across spliced exons, strand-aware, is the real work here.

THE SELF-CHECK THAT MAKES THIS TRUSTWORTHY
------------------------------------------
Exon lengths summed from the GTF must equal the FASTA sequence length,
for every transcript. If the coordinate walk is wrong, or the two
files are from different releases, this fails loudly instead of
storing quiet nonsense. Mismatches are reported and the transcript is
skipped, never guessed at.

ONE DELIBERATE COMPROMISE
-------------------------
`transcripts.entrez` and `genes.entrez` are NOT NULL and are the join
key used everywhere in this codebase. Ensembl files carry no Entrez
id, so the versionless Ensembl GENE id (ENSMUSG...) is stored in that
column for non-human species. Everything that joins on it keeps
working. The cost lands later: clusterProfiler wants real Entrez ids,
so GO/KEGG for these species needs a bitr() mapping step that does not
exist yet. Recorded, not solved.
"""

import argparse
import gzip
import os
import re
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import species as sp                                       # noqa: E402

ATTR = re.compile(r'(\S+) "([^"]*)"')


def _open(path):
    """Ensembl ships .gz; accept either."""
    return gzip.open(path, "rt") if path.endswith(".gz") else open(path)


def _ns(key, ident):
    """Namespace a primary key for an uploaded organism, else leave it.

    Shipped species keep their real identifiers, so nothing about the
    five changes. Only an upload gets a prefix, and only on the columns
    that must be unique across the whole table.
    """
    if not sp.is_upload(key):
        return ident
    return key[len(sp.UPLOAD_PREFIX):] + "|" + ident


def _attrs(field):
    """GTF column 9 to a dict. 'tag' repeats, so tags are collected."""
    out, tags = {}, []
    for key, val in ATTR.findall(field):
        if key == "tag":
            tags.append(val)
        else:
            out[key] = val
    out["tags"] = tags
    return out


# ---------------------------------------------------------------- GTF

def _has_canonical(path):
    """Whether this GTF marks canonical transcripts at all.

    Ensembl tags one transcript per gene with Ensembl_canonical, but
    only for the annotation it builds itself. WormBase, FlyBase and the
    plant divisions reach Ensembl without it.
    """
    for line in _open(path):
        if not line.startswith("#") and "Ensembl_canonical" in line:
            return True
    return False


def one_per_gene(tx):
    """Reduce to one transcript per gene: longest CDS, then longest.

    A no-op on a GTF that already carries canonical tags, since there
    is only one transcript per gene to choose from. The transcript id
    breaks ties, so the same GTF always gives the same answer.
    """
    best = {}
    for tid, rec in tx.items():
        gene = rec.get("gene") or tid
        cds = sum(b - a + 1 for a, b in rec.get("cds", []))
        exons = sum(b - a + 1 for a, b in rec.get("exons", []))
        score = (cds, exons, tid)
        if gene not in best or score > best[gene][0]:
            best[gene] = (score, tid)
    return {tid: tx[tid] for _, tid in best.values()}


def read_gtf(path):
    """{transcript_id: record}, one transcript per gene.

    Ensembl marks one transcript per gene with tag "Ensembl_canonical".
    That is the direct analogue of MANE Select: one transcript per
    gene, so a gene is counted once and never double-reported across
    isoforms.

    A GTF without that tag is not rejected. Everything is kept here
    and build() reduces it with one_per_gene().
    """
    canonical = _has_canonical(path)
    tx = {}
    kept = set()
    for line in _open(path):
        if line.startswith("#"):
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 9:
            continue
        feat = f[2]
        if feat not in ("transcript", "exon", "CDS", "stop_codon"):
            continue
        a = _attrs(f[8])
        tid = a.get("transcript_id")
        if not tid:
            continue

        if feat == "transcript":
            if canonical and "Ensembl_canonical" not in a["tags"]:
                continue
            kept.add(tid)
            tx[tid] = {
                "tid":      tid,
                "version":  a.get("transcript_version"),
                "gene":     a.get("gene_id"),
                "gene_ver": a.get("gene_version"),
                "symbol":   a.get("gene_name") or a.get("gene_id"),
                "biotype":  a.get("transcript_biotype", "unknown"),
                "strand":   f[6],
                "exons":    [],
                "cds":      [],
                "stop":     [],
            }
            continue

        if tid not in kept:
            continue
        span = (int(f[3]), int(f[4]))
        if feat == "exon":
            tx[tid]["exons"].append(span)
        elif feat == "CDS":
            tx[tid]["cds"].append(span)
        else:
            tx[tid]["stop"].append(span)
    return tx


# -------------------------------------------- genomic -> transcript

def exon_order(exons, strand):
    """Exons in transcript order: 5' first.

    On the minus strand the transcript runs right-to-left along the
    genome, so exon order is descending by genomic start. Getting this
    backwards silently puts the CDS at the wrong end of roughly half
    of all genes, which is exactly the kind of error that still
    produces believable-looking output.
    """
    return sorted(exons, key=lambda e: e[0], reverse=(strand == "-"))


def g2t(pos, exons, strand):
    """1-based transcript coordinate of a genomic position, or None."""
    offset = 0
    for start, end in exon_order(exons, strand):
        if start <= pos <= end:
            return offset + (pos - start + 1 if strand == "+"
                             else end - pos + 1)
        offset += end - start + 1
    return None


def cds_bounds(rec):
    """(cds_start, cds_end) in transcript coordinates, or (None, None).

    Ensembl's GTF excludes the stop codon from its CDS features, but
    the ORF genuinely ends after the stop. scanMiR is handed cds_end
    as ORF.length, so the three stop nucleotides belong inside it -
    otherwise the last codon reads as 3'UTR. The stop codon is always
    contiguous with the CDS in transcript coordinates even when it is
    split across two exons in the genome, so adding 3 is correct where
    a stop_codon feature is present.
    """
    if not rec["cds"]:
        return None, None
    strand, exons = rec["strand"], rec["exons"]
    if strand == "+":
        g_start = min(s for s, _ in rec["cds"])
        g_end = max(e for _, e in rec["cds"])
    else:
        g_start = max(e for _, e in rec["cds"])
        g_end = min(s for s, _ in rec["cds"])

    t_start = g2t(g_start, exons, strand)
    t_end = g2t(g_end, exons, strand)
    if t_start is None or t_end is None:
        return None, None
    if rec["stop"]:
        t_end += 3
    if t_start >= t_end:
        return None, None
    return t_start, t_end


def regions_of(length, cds_start, cds_end):
    """[(region, start, end)] - empty regions are never stored.

    A transcript with no CDS (lncRNA, or the canonical pick for a
    non-coding gene) gets no region rows at all, which is the same
    shape the human loader produces.
    """
    if not cds_start:
        return []
    out = []
    if cds_start > 1:
        out.append(("5UTR", 1, cds_start - 1))
    out.append(("CDS", cds_start, cds_end))
    if cds_end < length:
        out.append(("3UTR", cds_end + 1, length))
    return out


# -------------------------------------------------------------- FASTA

def read_fasta(path, wanted):
    """{transcript_id: sequence} for wanted ids only, keyed as the GTF.

    An Ensembl cDNA header carries the version - ENST00000123456.7 -
    where the GTF's transcript_id does not, so the version has to come
    off for the two to meet. WormBase and FlyBase ids are built from
    dots, F07C3.7.1, and already match the GTF exactly; stripping would
    destroy them. So the whole id is tried first and a trailing version
    removed only if that fails.

    Streamed and filtered so only the chosen transcripts are held in
    memory - the full cDNA file is several hundred MB unpacked.
    """
    seqs, tid, buf = {}, None, []
    for line in _open(path):
        if line.startswith(">"):
            if tid:
                seqs[tid] = "".join(buf)
            head = line[1:].split(None, 1)[0]
            if head in wanted:
                key = head
            else:
                stem = head.rsplit(".", 1)[0]
                key = stem if stem in wanted else None
            tid, buf = key, []
        elif tid:
            buf.append(line.strip())
    if tid:
        seqs[tid] = "".join(buf)
    return seqs


# --------------------------------------------------------------- build

def build(key, fasta_path, gtf_path, keep_noncoding=False):
    """Parse both files into rows. Returns (rows, problems, counts).

    Two kinds of transcript are left out, and they are reported
    separately because only one of them is a problem:

    `absent` - in the GTF but not in the FASTA. Ensembl splits its
    sequence files: cdna.all.fa holds protein-coding and pseudogene
    transcripts, while lncRNA, miRNA, snoRNA and friends ship in a
    separate ncrna.fa. For mouse that is ~42,000 transcripts and it
    is entirely expected, not an error.

    `noncoding` - present in the FASTA but with no CDS, i.e. the
    pseudogenes. Dropped by default so a species matches the shape of
    the human MANE Select set, which is protein-coding throughout.
    Keeping them would hand every tool ~14,000 extra transcripts that
    human never sees, quietly making cross-species comparisons
    unequal.

    `problems` is the list that actually matters: a length mismatch
    there means the FASTA and GTF are from different releases.
    """
    gtf = read_gtf(gtf_path)
    if not gtf:
        sys.exit("no transcripts found in the annotation file.")
    gtf = one_per_gene(gtf)

    # keyed by the GTF's own transcript_id; read_fasta meets it there
    by_base = {t: t for t in gtf}
    seqs = read_fasta(fasta_path, set(by_base))

    rows, problems = [], []
    counts = {"gtf": len(by_base), "absent": 0, "noncoding": 0}
    for base, tid in sorted(by_base.items()):
        rec = gtf[tid]
        seq = seqs.get(base)
        if seq is None:
            counts["absent"] += 1
            continue

        exon_len = sum(e - s + 1 for s, e in rec["exons"])
        if exon_len != len(seq):
            # The load-bearing check: GTF and FASTA disagree, so one
            # of them is from a different release. Skip, never guess.
            problems.append((base, "length %d (GTF) vs %d (FASTA)"
                             % (exon_len, len(seq))))
            continue

        cds_start, cds_end = cds_bounds(rec)
        if cds_end and cds_end > len(seq):
            problems.append((base, "cds_end %d past end %d"
                             % (cds_end, len(seq))))
            cds_start = cds_end = None

        if cds_start is None and not keep_noncoding:
            counts["noncoding"] += 1
            continue

        gene_base = (rec["gene"] or "").split(".")[0]
        full = base + ("." + rec["version"] if rec["version"] else "")
        rows.append({
            # transcripts.refseq and genes.entrez are primary keys across
            # the WHOLE table, not per species. A user uploading an
            # organism this installation already has - or re-uploading
            # their own - would otherwise collide with the existing rows
            # and the load would fail partway through. Their keys are
            # therefore namespaced with the upload's own id.
            #
            # refseq_base, ensembl and ensembl_base keep the original
            # identifiers, so someone who pastes ENSOCUT00000008772 still
            # finds their transcript: those lookups are species-scoped
            # already and do not need to be unique globally.
            "refseq":       _ns(key, full),
            "refseq_base":  base,
            "ensembl":      full,
            "ensembl_base": base,
            "entrez":       _ns(key, gene_base),  # see module docstring
            "symbol":       rec["symbol"],
            "length":       len(seq),
            "cds_start":    cds_start,
            "cds_end":      cds_end,
            "biotype":      rec["biotype"],
            "species":      key,
            "sequence":     seq,
            "gene_ensembl": rec["gene"],
            "gene_base":    gene_base,
            "regions":      regions_of(len(seq), cds_start, cds_end),
        })
    return rows, problems, counts


# ---------------------------------------------------------------- load

MIGRATE = """
Add the canonical flag before loading any non-human species:

    ALTER TABLE transcripts ADD COLUMN canonical INTEGER NOT NULL DEFAULT 0;
    UPDATE transcripts SET canonical = 1 WHERE mane_status = 'MANE Select';
    CREATE INDEX IF NOT EXISTS ix_tx_species ON transcripts(species, canonical);

Then replace every `mane_status='MANE Select'` filter in src/ and
scripts/ with `canonical=1 AND species=?`. Human results must come out
byte-identical afterwards - that is the regression test.
"""


def load(con, key, rows, fasta_path, gtf_path):
    cols = [r[1] for r in con.execute("PRAGMA table_info(transcripts)")]
    if "canonical" not in cols:
        sys.exit("transcripts has no `canonical` column.\n" + MIGRATE)

    con.execute("DELETE FROM regions WHERE refseq IN "
                "(SELECT refseq FROM transcripts WHERE species=?)", (key,))
    con.execute("DELETE FROM transcripts WHERE species=?", (key,))
    con.execute("DELETE FROM genes WHERE species=?", (key,))

    seen = set()
    for r in rows:
        con.execute(
            "INSERT INTO transcripts (refseq, refseq_base, ensembl, "
            "ensembl_base, entrez, symbol, mane_status, length, cds_start, "
            "cds_end, biotype, species, sequence, canonical) "
            "VALUES (?,?,?,?,?,?,NULL,?,?,?,?,?,?,1)",
            (r["refseq"], r["refseq_base"], r["ensembl"], r["ensembl_base"],
             r["entrez"], r["symbol"], r["length"], r["cds_start"],
             r["cds_end"], r["biotype"], r["species"], r["sequence"]))
        for region, start, end in r["regions"]:
            con.execute("INSERT INTO regions (refseq, region, start_pos, "
                        "end_pos, length) VALUES (?,?,?,?,?)",
                        (r["refseq"], region, start, end, end - start + 1))
        if r["gene_base"] not in seen:
            seen.add(r["gene_base"])
            con.execute("INSERT INTO genes (entrez, symbol, ensembl_gene, "
                        "ensembl_base, hgnc, description, species) "
                        "VALUES (?,?,?,?,NULL,NULL,?)",
                        (r["entrez"], r["symbol"], r["gene_ensembl"],
                         r["gene_base"], key))

    # A user-uploaded organism is not a registry species, so there is no
    # assembly or release to name. Provenance records what is actually
    # true of it - that a person supplied these two files - rather than
    # inventing a version string.
    if sp.is_upload(key):
        version = "user upload"
        url = None
        notes = ("transcripts and annotation supplied by the user; "
                 "canonical transcripts only; entrez column holds the "
                 "annotation's own gene id")
    else:
        version = "Ensembl %s (%s)" % (sp.ENSEMBL_RELEASE,
                                       sp.get(key)["assembly"])
        url = sp.fasta_url(key)
        notes = ("canonical transcripts only; entrez column holds the "
                 "Ensembl gene id (no Entrez mapping for this species)")
    con.execute(
        "INSERT OR REPLACE INTO data_sources (name, version, url, "
        "downloaded_on, bytes, sha256, notes) VALUES (?,?,?,?,?,NULL,?)",
        (sp.source_name(key), version, url, date.today().isoformat(),
         os.path.getsize(fasta_path) + os.path.getsize(gtf_path), notes))
    con.commit()


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    # Not restricted to the registry: an "upload:<id>" key is valid too,
    # which is what makes this script usable for debugging a user's
    # upload by hand.
    p.add_argument("species")
    p.add_argument("--fasta", required=True)
    p.add_argument("--gtf", required=True)
    p.add_argument("--db", default="data/processed/mirna.db")
    p.add_argument("--check", metavar="GENE",
                   help="print this gene's bounds and exit without writing")
    p.add_argument("--load", action="store_true", help="write to the database")
    p.add_argument("--keep-noncoding", action="store_true",
                   help="keep pseudogenes and other CDS-less transcripts")
    args = p.parse_args()
    try:
        sp.get(args.species)
    except ValueError as exc:
        sys.exit(str(exc))

    rows, problems, counts = build(args.species, args.fasta, args.gtf,
                                   args.keep_noncoding)

    n = lambda v: format(v, ",")                           # noqa: E731
    print("%-28s %s" % ("species", args.species))
    print("%-28s %s" % ("canonical in the GTF", n(counts["gtf"])))
    print("%-28s %s  (expected: ncrna.fa)"
          % ("  not in the cDNA FASTA", n(counts["absent"])))
    print("%-28s %s  (pseudogenes)"
          % ("  dropped, no CDS", n(counts["noncoding"])))
    print("%-28s %s" % ("LOADED", n(len(rows))))
    print("%-28s %s" % ("region rows",
                        n(sum(len(r["regions"]) for r in rows))))
    print("%-28s %s%s" % ("mismatches", n(len(problems)),
                          "" if not problems else "   <- INVESTIGATE"))
    for base, why in problems[:10]:
        print("    %-20s %s" % (base, why))
    if len(problems) > 10:
        print("    ... and %d more" % (len(problems) - 10))

    if args.check:
        want = args.check.lower()
        hit = [r for r in rows if r["symbol"].lower() == want]
        if not hit:
            sys.exit("\nno canonical transcript for %r" % args.check)
        r = hit[0]
        print("\n%s  %s  %d nt" % (r["symbol"], r["refseq"], r["length"]))
        print("  cds_start %s   cds_end %s" % (r["cds_start"], r["cds_end"]))
        for region, start, end in r["regions"]:
            print("  %-5s %7d - %-7d  %6d nt" % (region, start, end,
                                                 end - start + 1))
        print("\n  first 60 nt of CDS: %s"
              % r["sequence"][(r["cds_start"] or 1) - 1:][:60])
        print("  last 3 nt of CDS:   %s   <- expect a stop codon "
              "(TAA/TAG/TGA)" % r["sequence"][(r["cds_end"] or 3) - 3:
                                              r["cds_end"]])
        return

    if not args.load:
        print("\nnothing written. --load to write, --check GENE to inspect.")
        return

    con = sqlite3.connect(args.db)
    load(con, args.species, rows, args.fasta, args.gtf)
    print("\nloaded into %s" % args.db)


if __name__ == "__main__":
    main()
