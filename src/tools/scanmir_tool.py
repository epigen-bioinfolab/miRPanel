"""scanMiR 1.16.0, wrapped as a tool.

A CNN-derived affinity model (McGeary et al., Science 2019, trained on RNA
bind-n-seq) scores every candidate site on the transcript and predicts its
dissociation constant. Unlike TargetScan and miRDB it scans arbitrary
sequence, so 5'UTR, CDS and 3'UTR are all covered, and unlike either of them
it reports a position for every site.

Rules established by the evaluation (manifests/scanmir_design.md):
  - ORF.length must be supplied or the whole transcript is treated as 3'UTR
    and the ORF penalty (c = 0.181) is never applied
  - ORF.length is cds_end, not the CDS length: scanMiR models a transcript as
    ORF then 3'UTR and has no 5'UTR concept
  - maxLogKd is c(3'UTR cutoff, ORF cutoff), not a single value
  - log_kd comes back as an integer scaled by 1000: -2440 means -2.440
  - the model is chosen by mature sequence, never by name: scanMiRData was
    built on miRBase 22 and 864 of 2,656 human model names have since changed
  - a miRNA whose seed was revised in Release 23 has no usable model; the
    column reads N.A. rather than a number computed for a different molecule

The score stored is the per-site log Kd. The aggregated per-transcript
repression estimate is carried in `extra` rather than competing as a second
score, because it is strongly length-dependent (Spearman rho -0.60 against
transcript length) and would rank long transcripts above well-targeted ones.
"""
import json, os, shutil, subprocess, tempfile

import targets as T
from tools.registry import record

META = {"name": "scanmir", "version": "1.16.0", "kind": "prediction",
        "score_type": "log Kd", "better": "lower",
        "gives_position": True, "needs_sequence": True, "slow": True}

# scanMiR's own defaults, kept deliberately. See the manifest: a site-type rule
# hides weak sites at display time instead, so nothing is discarded at scan
# time that could not be recomputed only by scanning again.
MAX_LOG_KD_UTR = -1.0
MAX_LOG_KD_ORF = -1.5
SHADOW = 0

# Site classes strong enough to show by default. Everything else - the 6mer
# family and the large non-canonical tail - is flagged low_confidence. For
# hsa-miR-21-5p transcriptome-wide that tail is 76% of all sites, so without
# this flag scanMiR would bury every other tool in the results table.
STRONG = {"8mer", "7mer-m8", "7mer-a1", "7mer-A1",
          "wobbled 8mer", "wobbled 7mer",
          "g-bulged 8mer", "g-bulged 7mer"}

_HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(os.path.dirname(os.path.dirname(_HERE)),
                      "scripts", "scanmir_run.R")


def covers(con, entrez):
    """Any transcript we hold can be scanned."""
    return True


def _status(stdout):
    """The runner's key/value tail -> a dict.

    A line may carry a third field (STATUS carries OK plus how the model was
    matched). The value is always the second field; anything after it is kept
    under '<KEY>_MSG'. Folding the extra field into the value turned a
    successful run into a failure once already.
    """
    out = {}
    for line in stdout.splitlines():
        f = line.rstrip("\n").split("\t")
        if len(f) >= 2:
            out[f[0]] = f[1]
            if len(f) > 2:
                out[f[0] + "_MSG"] = "\t".join(f[2:])
    return out


def run(con, mirna, tgts, opts=None, progress=None):
    """Scan this miRNA against every target transcript."""
    opts = opts or {}
    kd_utr = float(opts.get("max_log_kd_utr", MAX_LOG_KD_UTR))
    kd_orf = float(opts.get("max_log_kd_orf", MAX_LOG_KD_ORF))
    shadow = int(opts.get("shadow", SHADOW))

    prov = {"tool": "scanmir", "version": META["version"],
            "params": {"max_log_kd_utr": kd_utr, "max_log_kd_orf": kd_orf,
                       "shadow": shadow, "keep_match_seq": True,
                       "coef_utr": 0, "coef_orf": 0,
                       "orf_length": "cds_end"}}

    # A revised seed is checked here as well as in the runner. The flag was
    # derived independently from the miRBase v22 -> v23 diff and agrees with
    # scanMiR's own model sequences on all 243 cases, so failing early costs
    # nothing and keeps the reason in one place.
    if mirna.get("seed_changed"):
        return {"records": [], "provenance": prov,
                "warnings": ["miRNA seed was revised in miRBase Release 23; "
                             "the scanMiR model predates the revision and "
                             "would predict a different molecule"]}

    refseqs = [t["refseq"] for t in tgts]
    seqs = T.sequences(con, refseqs)
    regs = T.regions(con, refseqs)
    by_refseq = {t["refseq"]: t for t in tgts if seqs.get(t["refseq"])}
    if not by_refseq:
        return {"records": [], "provenance": prov, "warnings": ["no sequences"]}

    cds_end = {r: (e or 0) for r, e in con.execute(
        "SELECT refseq, cds_end FROM transcripts")}

    work = tempfile.mkdtemp(prefix="scanmir_")
    try:
        tx = os.path.join(work, "tx.tsv")
        with open(tx, "w") as fh:
            for r in by_refseq:
                fh.write("%s\t%d\t%s\n" % (r, cds_end.get(r, 0) or 0, seqs[r]))

        sites_p = os.path.join(work, "sites.tsv")
        agg_p = os.path.join(work, "agg.tsv")
        proc = subprocess.run(
            ["Rscript", RUNNER, tx, mirna["name"], mirna["sequence"],
             sites_p, agg_p, str(kd_utr), str(kd_orf), str(shadow)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError("scanMiR runner failed: %s"
                               % (proc.stderr.strip()[:300] or "no stderr"))

        st = _status(proc.stdout)
        if st.get("STATUS") != "OK":
            # A missing or outdated model is not a failure of the run: it is
            # the honest answer "this tool cannot assess this miRNA", which the
            # interface renders as N.A. rather than as a dash.
            msg = proc.stdout.strip().splitlines()[0] if proc.stdout else "no status"
            return {"records": [], "provenance": prov, "warnings": [msg]}

        prov["params"]["model"] = st.get("MODEL")
        prov["params"]["model_sequence"] = st.get("MODEL_SEQ")
        prov["params"]["model_conservation"] = st.get("CONSERVATION")
        prov["version"] = st.get("SCANMIR", META["version"])
        prov["params"]["scanmirdata"] = st.get("SCANMIRDATA")
        prov["params"]["r_version"] = st.get("RVERSION")

        repression = {}
        counts = {}
        with open(agg_p) as fh:
            head = fh.readline().rstrip("\n").split("\t")
            idx = {h: i for i, h in enumerate(head)}
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if not f or not f[0]:
                    continue
                r = f[idx["refseq"]]
                try:
                    repression[r] = float(f[idx["repression"]])
                except (KeyError, ValueError):
                    repression[r] = None
                counts[r] = {h: f[i] for h, i in idx.items()
                             if h not in ("refseq", "repression")}

        out = []
        with open(sites_p) as fh:
            head = fh.readline().rstrip("\n").split("\t")
            idx = {h: i for i, h in enumerate(head)}
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) < len(head):
                    continue
                r = f[idx["refseq"]]
                t = by_refseq.get(r)
                if t is None:
                    continue
                start = int(f[idx["start"]])
                end = int(f[idx["end"]])
                stype = f[idx["type"]]
                raw = int(f[idx["log_kd"]])
                p3 = f[idx["p3_score"]]
                note = f[idx["note"]]
                mseq = f[idx["match_seq"]]
                orf = f[idx["orf"]]
                out.append(record(
                    mirna, t, "scanmir",
                    # scanMiR's ORF flag folds the 5'UTR in with the ORF; our
                    # own regions table is the authority for which region a
                    # position actually falls in.
                    region=T.region_of(regs.get(r, []), start),
                    site_type=stype, pos_start=start, pos_end=end,
                    score=raw / 1000.0, score_type=META["score_type"],
                    low_confidence=(stype not in STRONG),
                    extra=json.dumps({
                        "log_kd_scaled_int": raw,
                        "p3_score": None if p3 in ("", "NA") else int(p3),
                        "match_sequence": mseq or None,
                        "note": None if note in ("", "-", "NA") else note,
                        "scanmir_orf_region": (orf == "TRUE"),
                        "transcript_repression": repression.get(r),
                        "transcript_site_counts": counts.get(r)})))

        warn = []
        how = st.get("STATUS_MSG") or ""
        if "3' end differs" in how:
            warn.append("scanMiR model sequence differs from miRBase R23 "
                        "outside the seed; sites are unaffected but p3_score "
                        "is computed from the older 3' end")
        if proc.stderr.strip():
            warn.append(proc.stderr.strip()[:300])
    finally:
        shutil.rmtree(work, ignore_errors=True)

    return {"records": out, "provenance": prov, "warnings": warn}
