"""Build a standing HTML report for one job.

Why this is queued rather than computed in the request: a report reads every
row of a job, aggregates them per gene, and renders an enrichment run
alongside. That is seconds, not milliseconds, and it follows the same rule
as jobs and enrichment - nothing slow happens inside an HTTP request.

Why it is a summary and says so: a transcriptome-wide job is 58,954 rows. A
report containing all of them would be tens of megabytes and would not open.
So the report carries the top N genes in the order the reader chose, and
states at the top - not in a footnote - how many genes it is showing out of
how many, with the TSV named as the place every row lives. A report that
looked complete while showing 0.8% of the data would be worse than no report.

The provenance block at the end is the same text the TSV carries, generated
by the same code. The two can never claim different versions.
"""
import datetime, html, json, uuid

import config
import provenance
import ranking
import svg as SVG

# Every column an aggregated gene row needs, fetched once for all the genes
# that made the cut rather than per gene.
ROW_COLS = ("symbol", "entrez", "refseq", "region", "tool", "site_type",
            "pos_start", "pos_end", "score", "score_type", "low_confidence",
            "extra")

REGION_LABEL = {"5UTR": "5′UTR", "CDS": "CDS", "3UTR": "3′UTR"}
REGION_ORDER = ["5UTR", "CDS", "3UTR"]

# Ranked best first, matching the seed analyser's published categories.
SITE_RANK = ["8mer", "7mer-m8", "7mer-A1", "6mer"]


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _esc(v):
    return html.escape("" if v is None else str(v))


# ------------------------------------------------------------------ queue

def create(con, job_id, spec):
    """Register a report and queue it. Fast: it resolves nothing heavy.

    The spec is fixed here rather than at render time, so a report answers
    the question that was actually asked even if it waits in the queue.
    """
    j = con.execute("SELECT finished_at, status FROM jobs WHERE job_id=?",
                    (job_id,)).fetchone()
    if j is None:
        raise ValueError("no such job: " + job_id)
    if j[1] != "done":
        raise ValueError("job is %s; a report needs a finished job" % j[1])
    spec = dict(spec or {})
    spec.setdefault("sort", "gene")
    spec.setdefault("top_n", 50)
    # Same decision as the results panel: 20 per ontology, never one mixed
    # ranking. Printing all 232 GO:BP terms turned a nine-gene report into
    # seventeen pages, and the complete list already lives in the terms TSV.
    spec.setdefault("terms_per_source", 20)
    # A map is per gene, so fifty of them is a document nobody scrolls. The
    # best-supported handful is a figure; the rest are in the TSV.
    spec.setdefault("maps_for", 10)
    spec.setdefault("network", True)
    try:
        ranking.gene_order(spec["sort"])
    except ranking.BadSort as e:
        raise ValueError(str(e))
    # the newest completed enrichment, if the user ever ran one - recorded now
    # so the report cannot silently pick up a different one later
    enr = con.execute("SELECT run_id FROM enrichment_runs WHERE job_id=? AND "
                      "status='done' ORDER BY created_at DESC LIMIT 1",
                      (job_id,)).fetchone()
    report_id = "rep_" + uuid.uuid4().hex[:12]
    con.execute("INSERT INTO reports (report_id, job_id, job_finished_at, "
                "created_at, status, spec_json, enrichment_run) "
                "VALUES (?,?,?,?,?,?,?)",
                (report_id, job_id, j[0], now(), "queued", json.dumps(spec),
                 enr[0] if enr else None))
    con.commit()
    return report_id


def next_queued(con):
    """Atomically claim the oldest queued report. Returns report_id or None."""
    row = con.execute("SELECT report_id FROM reports WHERE status='queued' "
                      "ORDER BY created_at LIMIT 1").fetchone()
    if row is None:
        return None
    cur = con.execute("UPDATE reports SET status='running', started_at=? "
                      "WHERE report_id=? AND status='queued'", (now(), row[0]))
    con.commit()
    return row[0] if cur.rowcount else None


def requeue_stale(con):
    """Put reports left 'running' by a crashed worker back in the queue."""
    cur = con.execute("UPDATE reports SET status='queued', started_at=NULL "
                      "WHERE status='running'")
    con.commit()
    return cur.rowcount


def get(con, report_id, include_html=False):
    cols = ("report_id", "job_id", "job_finished_at", "created_at",
            "started_at", "finished_at", "status", "error", "spec_json",
            "enrichment_run", "n_genes", "bytes", "seconds")
    row = con.execute("SELECT " + ", ".join(cols) + " FROM reports "
                      "WHERE report_id=?", (report_id,)).fetchone()
    if row is None:
        return None
    r = dict(zip(cols, row))
    r["spec"] = json.loads(r.pop("spec_json"))
    job = con.execute("SELECT finished_at FROM jobs WHERE job_id=?",
                      (r["job_id"],)).fetchone()
    # the job may have been re-run since; a report about a job that no longer
    # exists in that form is still a real result, so say so rather than hide it
    r["stale"] = bool(job and job[0] != r["job_finished_at"])
    if include_html:
        r["html"] = con.execute("SELECT html FROM reports WHERE report_id=?",
                                (report_id,)).fetchone()[0]
    return r


def list_reports(con, job_id):
    cols = ("report_id", "created_at", "status", "n_genes", "bytes", "seconds")
    return [dict(zip(cols, r)) for r in con.execute(
        "SELECT " + ", ".join(cols) + " FROM reports WHERE job_id=? "
        "ORDER BY created_at DESC", (job_id,))]


# ------------------------------------------------------------- gathering

def _gene_rows(con, job_id, spec):
    """The top N genes in the chosen order, and every stored row for them."""
    order, oargs = ranking.gene_order(spec["sort"])
    total = con.execute("SELECT COUNT(DISTINCT symbol) FROM results "
                        "WHERE job_id=?", (job_id,)).fetchone()[0]
    syms = [r[0] for r in con.execute(
        "SELECT symbol FROM results WHERE job_id=? GROUP BY symbol "
        "ORDER BY " + order + " LIMIT ?",
        [job_id] + oargs + [int(spec["top_n"])])]
    if not syms:
        return [], {}, total
    qs = ",".join("?" * len(syms))
    rows = con.execute("SELECT " + ", ".join(ROW_COLS) + " FROM results "
                       "WHERE job_id=? AND symbol IN (" + qs + ") "
                       "ORDER BY symbol, tool, pos_start",
                       [job_id] + syms).fetchall()
    by_gene = {s: [] for s in syms}
    for r in rows:
        d = dict(zip(ROW_COLS, r))
        d["extra"] = json.loads(d["extra"]) if d["extra"] else None
        by_gene[d["symbol"]].append(d)
    return syms, by_gene, total


def summarise(rows):
    """One gene's stored rows reduced to what the table shows.

    Every tool keeps its own cell. Nothing here combines two tools' numbers
    into one, and a tool that did not run leaves its cell empty rather than
    borrowing another tool's answer.
    """
    seed = [r for r in rows if r["tool"] == "seed"]
    rh = [r for r in rows if r["tool"] == "rnahybrid"]
    ts = [r for r in rows if r["tool"] == "targetscan"]
    mt = [r for r in rows if r["tool"] == "mirtarbase"]
    best_seed = min(seed, key=lambda r: SITE_RANK.index(r["site_type"])
                    if r["site_type"] in SITE_RANK else 99) if seed else None
    best_rh = min(rh, key=lambda r: (r["score"] is None, r["score"])) if rh else None
    best_ts = min(ts, key=lambda r: (r["score"] is None, r["score"])) if ts else None
    regions = sorted({r["region"] for r in rows if r["region"]},
                     key=lambda x: REGION_ORDER.index(x)
                     if x in REGION_ORDER else 99)
    return {"refseq": rows[0]["refseq"], "entrez": rows[0]["entrez"],
            "regions": regions, "n_seed": len(seed), "n_rh": len(rh),
            "seed": best_seed, "rh": best_rh, "ts": best_ts,
            "mt": mt[0] if mt else None}


# --------------------------------------------------------------- render

def _geometry(con, symbols):
    """MANE Select transcript length and region bounds, per gene symbol."""
    import targets as T
    if not symbols:
        return {}
    qs = ",".join("?" * len(symbols))
    rows = con.execute("SELECT symbol, refseq, length FROM transcripts "
                       "WHERE symbol IN (" + qs + ") AND "
                       "mane_status='MANE Select'", list(symbols)).fetchall()
    regs = T.regions(con, [r[1] for r in rows])
    return {r[0]: {"refseq": r[1], "length": r[2],
                   "regions": sorted(regs.get(r[1], []), key=lambda x: x[1])}
            for r in rows}


def _maps_section(con, syms, by_gene, limit):
    """A binding map for the best-supported genes, in the report's own order."""
    if not limit or not syms:
        return ""
    shown = syms[:int(limit)]
    geom = _geometry(con, shown)
    out = ["<h2>Binding sites</h2>",
           "<p class='note'>One transcript per picture &mdash; the MANE "
           "Select transcript that was scanned &mdash; drawn to scale. A "
           "position only means anything against the sequence it was measured "
           "on. The two lanes are kept apart on purpose: the seed analyser "
           "reports a category at a point, RNAhybrid reports an energy over a "
           "span, and drawing them on one line would imply they are the same "
           "measurement.</p>"]
    if len(shown) < len(syms):
        out.append("<p class='note'>Maps are drawn for the first %d of %d "
                   "genes in this report.</p>" % (len(shown), len(syms)))
    drew = 0
    for s in shown:
        g = geom.get(s)
        if not g or not g["length"]:
            continue
        rows = by_gene[s]
        seed = [r for r in rows if r["tool"] == "seed"
                and r["pos_start"] is not None]
        rh = [r for r in rows if r["tool"] == "rnahybrid"
              and r["pos_start"] is not None]
        if not seed and not rh:
            continue
        out.append("<div class='mapblock'>")
        out.append(SVG.binding_map(s, g["refseq"], g["length"], g["regions"],
                                   seed, rh))
        out.append("</div>")
        drew += 1
    if not drew:
        return ("<h2>Binding sites</h2><p class='note'>No gene in this report "
                "has a positioned site to draw: miRTarBase evidence and "
                "TargetScan scores are reported per gene rather than at a "
                "coordinate on this transcript.</p>")
    return "".join(out)


def _network_section(con, job_id, spec):
    """The target network, laid out here so the same job gives one picture."""
    import network as NET
    try:
        data = NET.build(con, job_id, sort=spec["sort"],
                         top_n=int(spec["top_n"]))
    except Exception as exc:
        # a failed figure must not take the whole report down, but it must
        # not vanish either - a reader has to know a section is missing
        return ("<h2>Target network</h2><p class='note'>The network could "
                "not be drawn for this report: %s</p>" % _esc(repr(exc)))
    if len(data["nodes"]) < 2:
        return ("<h2>Target network</h2><p class='note'>This job produced no "
                "genes, so there is nothing to draw.</p>")
    body, dropped = SVG.network(data)
    m = data["meta"]
    out = ["<h2>Target network</h2>", body,
           "<div class='netkey-svg'>"
           "<span><b style='background:#1f4e79'></b>miRNA</span>"
           "<span><b style='background:#e2f1e8;border:1.5px solid #1a6b3c'>"
           "</b>validated target (miRTarBase)</span>"
           "<span><b style='background:#eaeff4;border:1.5px solid #1f4e79'>"
           "</b>predicted only</span>"
           "<span>solid line — a tool reported this target; thicker means "
           "more tools agree</span>"
           "<span>dotted line — the two genes share enriched terms</span>"
           "</div>"]
    note = ["Line thickness is tool agreement, which is the only cross-tool "
            "number here: the tools' scores are on different scales and are "
            "never combined."]
    if dropped:
        note.append("%d further genes are not drawn; the best-supported %d "
                    "are shown." % (dropped, SVG.MAX_NODES))
    if m["shared_layer"]:
        note.append("%d of these genes carry shared-term links, from "
                    "enrichment run %s."
                    % (m["genes_in_shared_layer"], m["enrichment_run"]))
    else:
        note.append("No pathway analysis had been run when this report was "
                    "requested, so genes are not linked to each other.")
    note.append("The layout is computed from the data rather than by physics "
                "in a browser, so the same job always gives the same picture.")
    out.append("<p class='note'>%s</p>" % " ".join(_esc(x) for x in note))
    return "".join(out)


CSS = SVG.CSS + """
.mapblock{margin:0 0 6px;padding:9px 11px 4px;border:1px solid var(--line);
  border-radius:5px;background:#fff}
:root{--ink:#15181d;--muted:#666f7a;--faint:#8a929c;--line:#e3e6ea;
  --accent:#1f4e79;--band:#f6f7f9}
*{box-sizing:border-box}
body{margin:0;padding:34px 30px 60px;background:#fff;color:var(--ink);
  font:14px/1.55 'Inter',system-ui,-apple-system,Segoe UI,sans-serif;
  max-width:1080px;margin-inline:auto}
h1{font-size:23px;margin:0 0 3px;letter-spacing:-.01em}
h2{font-size:15px;margin:34px 0 11px;padding-bottom:6px;
  border-bottom:1px solid var(--line);letter-spacing:-.005em}
.sub{color:var(--muted);margin:0 0 2px;font-size:13px}
.scope{margin:17px 0 0;padding:11px 13px;background:var(--band);
  border-left:3px solid var(--accent);border-radius:0 5px 5px 0;font-size:13px}
.stale{margin:11px 0 0;padding:10px 13px;border-left:3px solid #b4720e;
  background:#fdf6ec;border-radius:0 5px 5px 0;font-size:13px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:0}
th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line);
  vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.045em;
  color:var(--muted);font-weight:600;white-space:nowrap}
td.num,th.num{text-align:right;
  font-family:'JetBrains Mono',SFMono-Regular,Menlo,monospace}
tbody tr:nth-child(even){background:#fafbfc}
.gene{font-weight:600}
.txid{display:block;color:var(--faint);font-size:11px;
  font-family:'JetBrains Mono',SFMono-Regular,Menlo,monospace}
.tag{display:inline-block;padding:1px 6px;margin-right:3px;border-radius:3px;
  background:var(--band);border:1px solid var(--line);font-size:10.5px}
.none{color:var(--faint)}
.val{color:#1a6b3c;font-weight:600}
.sub2{display:block;color:var(--faint);font-size:10.5px}
pre.prov{white-space:pre-wrap;word-break:break-word;background:var(--band);
  border:1px solid var(--line);border-radius:5px;padding:13px 15px;
  font:11px/1.6 'JetBrains Mono',SFMono-Regular,Menlo,monospace;color:#394049}
.note{color:var(--muted);font-size:12.5px;margin:9px 0 0}
footer{margin-top:38px;padding-top:13px;border-top:1px solid var(--line);
  color:var(--faint);font-size:11.5px}
@media print{
  body{padding:0;max-width:none;font-size:11.5px}
  h2{page-break-after:avoid}
  table{page-break-inside:auto}
  tr{page-break-inside:avoid}
  .scope,.stale{border-left-width:2px}
}
"""


def _tools_table(st):
    out = ['<table><thead><tr><th>Tool</th><th>Status</th>'
           '<th class="num">Rows</th><th class="num">Seconds</th>'
           '<th>Message</th></tr></thead><tbody>']
    for t in st["tools"]:
        out.append("<tr><td>%s</td><td>%s</td><td class='num'>%s</td>"
                   "<td class='num'>%s</td><td>%s</td></tr>"
                   % (_esc(t["tool"]), _esc(t["status"]),
                      _esc(t["n_results"]), _esc(t["seconds"]),
                      _esc(t["message"] or "")))
    return "".join(out) + "</tbody></table>"


def _gene_table(syms, by_gene):
    head = ("<table><thead><tr><th>Gene</th><th>Regions</th>"
            "<th>Seed site</th><th class='num'>Position</th>"
            "<th class='num'>RNAhybrid ΔG</th>"
            "<th class='num'>TargetScan context++</th>"
            "<th>miRTarBase</th></tr></thead><tbody>")
    out = [head]
    for s in syms:
        g = summarise(by_gene[s])
        seed = g["seed"]
        rh, ts, mt = g["rh"], g["ts"], g["mt"]
        regions = "".join('<span class="tag">%s</span>' % REGION_LABEL.get(r, r)
                          for r in g["regions"]) or '<span class="none">—</span>'
        site = ('%s%s' % (_esc(seed["site_type"]),
                          '<span class="sub2">%d sites total</span>' % g["n_seed"]
                          if g["n_seed"] > 1 else "")
                if seed else '<span class="none">—</span>')
        pos = ('%s–%s<span class="sub2">%s</span>'
               % (seed["pos_start"], seed["pos_end"],
                  REGION_LABEL.get(seed["region"], seed["region"] or ""))
               if seed else '<span class="none">—</span>')
        dg = ('%.1f%s' % (rh["score"],
                          '<span class="sub2">best of %d foldings</span>' % g["n_rh"]
                          if g["n_rh"] > 1 else "")
              if rh and rh["score"] is not None else '<span class="none">—</span>')
        # TargetScan scores 3'UTRs only: a gene with no 3'UTR evidence at all
        # is outside what it can assess, which is not the same as a miss
        if ts and ts["score"] is not None:
            tsc = "%.3f" % ts["score"]
        elif "3UTR" in g["regions"]:
            tsc = '<span class="none">—</span>'
        else:
            tsc = '<span class="none">N.A.</span>'
        if mt:
            ex = mt["extra"] or {}
            tag = "validated" if str(ex.get("status", "")).startswith("validated") \
                else str(ex.get("status", "reported")).replace("_", " ")
            n = ex.get("strong_functional")
            mtc = ('<span class="val">%s</span>%s'
                   % (_esc(tag),
                      '<span class="sub2">%s strong functional</span>' % n
                      if n else ""))
        else:
            mtc = '<span class="none">—</span>'
        out.append("<tr><td><span class='gene'>%s</span>"
                   "<span class='txid'>%s</span></td><td>%s</td><td>%s</td>"
                   "<td class='num'>%s</td><td class='num'>%s</td>"
                   "<td class='num'>%s</td><td>%s</td></tr>"
                   % (_esc(s), _esc(g["refseq"]), regions, site, pos, dg,
                      tsc, mtc))
    return "".join(out) + "</tbody></table>"


def _enrichment_section(con, run_id, cap=20):
    import enrichment as E
    r = E.get_run(con, run_id)
    if r is None:
        return ""
    # already ordered by adjusted p, so the first `cap` of each group are the
    # strongest terms in that ontology
    terms = E.terms(con, run_id, None, None, 0, None)
    by_source = {}
    for t in terms:
        by_source.setdefault(t["source"], []).append(t)
    out = ['<h2>Pathway analysis</h2>',
           '<p class="sub">%s</p>' % _esc(r["rule_sentence"]),
           '<p class="note">%s of %s selected genes were annotated. Background: '
           '%s (%s %s), %s genes. Correction: %s.</p>'
           % (_esc(r["n_genes_annotated"]), _esc(r["n_genes"]),
              _esc(r["background"]), _esc(r["background_source"]),
              _esc(r["background_version"]), _esc(r["n_background"]),
              _esc(r["p_adjust_method"]))]
    if not terms:
        return "".join(out) + '<p class="note">No terms passed the cutoffs.</p>'
    # Never one mixed ranking: each ontology is tested against a different
    # annotated background, so a shared ordering would compare unlike numbers.
    for source in sorted(by_source):
        allrows = by_source[source]
        rows = allrows[:cap] if cap else allrows
        label = ("showing the top %d of %d terms" % (len(rows), len(allrows))
                 if len(rows) < len(allrows) else "%d terms" % len(allrows))
        out.append("<h2>%s <span class='sub'>&mdash; %s</span></h2>"
                   % (_esc(source), _esc(label)))
        out.append("<table><thead><tr><th>Term</th><th>ID</th>"
                   "<th class='num'>Genes</th><th class='num'>k / n</th>"
                   "<th class='num'>K / N</th><th class='num'>p</th>"
                   "<th class='num'>Adjusted p</th></tr></thead><tbody>")
        for t in rows:
            out.append("<tr><td>%s</td><td>%s</td><td class='num'>%s</td>"
                       "<td class='num'>%s / %s</td><td class='num'>%s / %s</td>"
                       "<td class='num'>%.2e</td><td class='num'>%.2e</td></tr>"
                       % (_esc(t["description"]), _esc(t["term_id"]),
                          _esc(t["k_in_term_and_list"]),
                          _esc(t["k_in_term_and_list"]), _esc(t["n_in_list"]),
                          _esc(t["k_in_term_and_background"]),
                          _esc(t["n_in_background"]),
                          t["p_value"], t["p_adjust"]))
        out.append("</tbody></table>")
    out.append('<p class="note">k / n and K / N are the four integers of each '
               'term’s own hypergeometric test. They are per ontology, not '
               'per run: each ontology annotates a different part of the '
               'genome, so every p-value above can be recomputed from its own '
               'row without R. Where a table is capped, the complete list of '
               'terms is in the enrichment TSV export.</p>')
    return "".join(out)


LEGEND = """
<h2>How to read this</h2>
<p class="note">Each column is one tool reporting on its own scale. Nothing in
this document combines two tools into a single score, because their scales
measure different things and averaging them would invent a number none of
them reported.</p>
<table><thead><tr><th>Column</th><th>What it is</th>
<th>Which way is better</th></tr></thead><tbody>
<tr><td><b>Gene</b></td><td>Symbol, and beneath it the MANE Select transcript
that was scanned. Every position in the row is measured along that
transcript.</td><td class="none">—</td></tr>
<tr><td><b>Regions</b></td><td>Which parts of the transcript had any hit at
all.</td><td class="none">—</td></tr>
<tr><td><b>Seed site</b></td><td>The strongest Watson–Crick seed match found
by the seed analyser.</td><td>8mer &gt; 7mer-m8 &gt; 7mer-A1 &gt; 6mer</td></tr>
<tr><td><b>Position</b></td><td>Where that strongest site sits, and in which
region.</td><td class="none">—</td></tr>
<tr><td><b>RNAhybrid ΔG</b></td><td>Folding free energy of the tightest
predicted duplex, kcal/mol. G:U wobbles count, so a tight duplex is not by
itself evidence of targeting.</td><td>more negative = tighter</td></tr>
<tr><td><b>TargetScan context++</b></td><td>TargetScan's own site score,
joined by seed family.</td><td>more negative = more repression</td></tr>
<tr><td><b>miRTarBase</b></td><td>Published experimental evidence, with the
number of strong functional experiments behind it.</td>
<td>evidence, not prediction</td></tr>
</tbody></table>
<p class="note"><b>An empty cell (—) and N.A. are not the same thing.</b>
— means the tool ran and reported no value. N.A. means the tool cannot
assess that gene at all: TargetScan scores 3′UTRs, so a gene with no 3′UTR
evidence is outside what it can judge rather than a miss.</p>
<p class="note"><b>Prediction does not track evidence.</b> A gene can carry
the weakest predicted score on the page and the largest published literature
behind it. Both columns are shown so that disagreement stays visible instead
of being averaged away.</p>
"""


def render(con, report_id):
    """Compose the HTML. Pure: reads the database, returns a string."""
    import orchestrator

    rep = get(con, report_id)
    spec = rep["spec"]
    st = orchestrator.job_status(con, rep["job_id"])
    syms, by_gene, total_genes = _gene_rows(con, rep["job_id"], spec)
    p = st["params"]

    shown = len(syms)
    scope = ("Showing the top <b>%d</b> of <b>%s</b> genes, ranked by %s. "
             "This is a summary: every one of the %s stored rows is in the "
             "TSV export, not here."
             % (shown, "{:,}".format(total_genes), _esc(spec["sort"]),
                "{:,}".format(st["n_results"] or 0)))
    if shown >= total_genes:
        scope = ("Showing all <b>%d</b> genes in this job, ranked by %s."
                 % (shown, _esc(spec["sort"])))

    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<title>%s — %s</title>" % (_esc(config.TOOL_NAME),
                                              _esc(p["mirna_name"])),
             "<style>%s</style></head><body>" % CSS,
             "<h1>%s</h1>" % _esc(p["mirna_name"]),
             "<p class='sub'>%s %s &middot; job %s &middot; generated %s</p>"
             % (_esc(config.TOOL_NAME), _esc(config.TOOL_VERSION),
                _esc(rep["job_id"]), _esc(now().replace("T", " ")))]
    if rep["stale"]:
        parts.append("<p class='stale'>This job has been re-run since this "
                     "report was requested. The numbers below are the ones "
                     "that existed when it was asked for.</p>")
    parts.append("<p class='scope'>%s</p>" % scope)

    parts.append("<h2>Tools run</h2>")
    parts.append(_tools_table(st))

    parts.append(LEGEND)

    parts.append("<h2>Genes</h2>")
    parts.append(_gene_table(syms, by_gene) if syms else
                 "<p class='note'>This job produced no rows.</p>")
    parts.append("<p class='note'>Each column is one tool on its own scale. "
                 "Nothing here is combined into a single score, and an empty "
                 "cell means that tool reported no value — N.A. means it "
                 "cannot assess that gene at all.</p>")

    if syms:
        parts.append(_maps_section(con, syms, by_gene,
                                   spec.get("maps_for", 10)))

    if rep["enrichment_run"]:
        parts.append(_enrichment_section(con, rep["enrichment_run"],
                                         spec.get("terms_per_source", 20)))
    else:
        parts.append("<h2>Pathway analysis</h2><p class='note'>No pathway "
                     "analysis had been run on this job when the report was "
                     "requested.</p>")

    if spec.get("network", True):
        parts.append(_network_section(con, rep["job_id"], spec))

    # The same lines the TSV carries, from the same function, so a reader
    # comparing the two files can never find them claiming different versions.
    parts.append("<h2>Provenance</h2><pre class='prov'>%s</pre>"
                 % _esc("\n".join(provenance.results(con, st))))
    parts.append("<footer>%s %s &middot; report %s</footer>"
                 % (_esc(config.TOOL_NAME), _esc(config.TOOL_VERSION),
                    _esc(report_id)))
    parts.append("</body></html>")
    return "".join(parts), shown


def execute(con, report_id):
    """Render a queued report and store it. Slow half; the worker calls this."""
    import time
    t0 = time.time()
    try:
        body, shown = render(con, report_id)
    except Exception as exc:
        con.execute("UPDATE reports SET status='failed', finished_at=?, "
                    "error=? WHERE report_id=?", (now(), repr(exc), report_id))
        con.commit()
        raise
    con.execute("UPDATE reports SET status='done', finished_at=?, html=?, "
                "n_genes=?, bytes=?, seconds=? WHERE report_id=?",
                (now(), body, shown, len(body.encode("utf-8")),
                 round(time.time() - t0, 3), report_id))
    con.commit()
    return report_id
