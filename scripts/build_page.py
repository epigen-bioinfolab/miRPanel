"""Compose web/index.html from the approved layout: same CSS, same render
code, but the data comes from the API instead of being typed in.

    python scripts/build_page.py

Reads web/layout-source.html - the page as it was designed and approved,
with its mock data still in it - and rewrites it into the live page: fonts
swapped, mock constants replaced by fetch calls, query and pathway panels
added.

Do not edit web/index.html by hand. It is generated, and the next build
overwrites it without asking. Edit the source layout or this script instead.
"""
import pathlib, re

HERE = pathlib.Path(__file__).resolve().parent.parent
SRC = HERE / "web" / "layout-source.html"
OUT = HERE / "web" / "index.html"
raw = SRC.read_text()

style = raw[raw.index("<style>") + 7: raw.index("</style>")]
FONTS = [("'Fraunces',Georgia,serif", "'Inter',system-ui,sans-serif"),
         ("'IBM Plex Sans',system-ui,sans-serif", "'Inter',system-ui,sans-serif"),
         ("'JetBrains Mono','SFMono-Regular',Menlo,monospace", "'JetBrains Mono','SFMono-Regular',Menlo,monospace")]
for _a, _b in FONTS:
    style = style.replace(_a, _b)
body = raw[raw.index('<div class="wrap">'): raw.index("<script>")]
script = raw[raw.index("<script>") + 8: raw.rindex("</script>")]

# ---- body: drop the mock masthead and the query-shape strip -----------------
keep = body[body.index('<section class="context">'):]
keep = keep[:keep.rindex("</div>")]          # drop the wrap close, we re-add it

# the mock's fixed job id and query-shape label become live fields
for old, new in [('<h2>Query<em>miRNA only</em></h2>', '<h2>Query<em id="qscope"></em></h2>'),
                 ('<h2>Tools run<em>job_46def2d032c6</em></h2>',
                  '<h2>Tools run<em id="runid"></em></h2>')]:
    assert keep.count(old) == 1, old
    keep = keep.replace(old, new)

# the notes named genes that happened to be in the mock run; generalise them
NOTE_SUBS = [
 ("<b>Look at GAPDH.</b> RNAhybrid gives it a stronger duplex (−20.6) than the textbook miR-21 target PDCD4 (−18.5) — but its seed pairing uses G:U wobbles, TargetScan has nothing, and no one has ever reported it. Energy alone would rank a housekeeping gene above the real target. That is the whole argument for keeping the columns apart.",
  "<b>A tight duplex is not evidence.</b> RNAhybrid regularly gives a housekeeping gene a stronger ΔG than a validated target, because folding energy is all it measures and G:U wobbles count. Ranking by energy alone would put such a gene above the real one. That is the whole argument for keeping the columns apart."),
 ("<b>Look at ABHD12B.</b> The strongest context++ on this page (−0.693) with no conservation support at all, and no experimental record. A confident prediction from one tool and silence from the rest.",
  "<b>Watch for one loud tool.</b> A strong context++ with no conservation and no published test is a confident prediction from one method and silence from the other three — worth a second look, not a conclusion."),
]
for _a, _b in NOTE_SUBS:
    assert keep.count(_a) == 1, _a[:40]
    keep = keep.replace(_a, _b)

# the pathway-analysis panel goes between the table and the notes
_notes = keep.index('<div class="notes">')
keep = keep[:_notes] + """<section class="panel" id="enrich">
    <h2>Pathway analysis<em id="gscount">nothing selected</em></h2>
    <div class="panel-body">
      <div class="gsgrid" id="gsboxes"></div>
      <div class="gsbar">
        <div class="fgroup" id="gsregions">
          <span>Regions</span>
          <label><input type="checkbox" value="5UTR" checked> 5\u2032UTR</label>
          <label><input type="checkbox" value="CDS" checked> CDS</label>
          <label><input type="checkbox" value="3UTR" checked> 3\u2032UTR</label>
        </div>
        <div class="fgroup" id="gsmatch" hidden>
          <span>Match</span>
          <label><input type="radio" name="gsm" value="all" checked> AND \u2014 a gene must pass every ticked box</label>
          <label><input type="radio" name="gsm" value="any"> OR \u2014 a gene passing any one box counts</label>
        </div>
      </div>
      <div class="gsfoot">
        <span class="say" id="gssentence"></span>
        <button class="go" id="gsrun" type="button" disabled>Run GO and KEGG</button>
      </div>
    </div>
  </section>

  <section class="panel" id="enrichout" hidden>
    <h2>Enriched terms<em id="enrichstate"></em></h2>
    <div class="panel-body">
      <p id="enrichhead"></p>
      <p id="enrichmeta"></p>
      <div class="tabs" id="enrichtabs"></div>
      <div class="tsearch">
        <label for="termq">Search pathways and terms</label>
        <div class="tsbox">
          <input type="search" id="termq" autocomplete="off"
                 placeholder="name or ID — mesenchyme, GO:0060485, hsa05206">
          <button type="button" id="termqx" hidden aria-label="clear">×</button>
        </div>
      </div>
      <table class="terms"><thead><tr>
        <th></th><th>Term</th><th>Genes</th><th>Adjusted p</th>
      </tr></thead><tbody id="termbody"></tbody></table>
      <div class="termfoot">
        <span id="termcount"></span>
        <button class="linkbtn" id="termmore" type="button" hidden></button>
      </div>
    </div>
  </section>

  """ + keep[_notes:]

# ---- script surgery --------------------------------------------------------
a = "  var MIR = {name:"
b = "  var SITE_RANK="
assert script.count(a) == 1 and script.count(b) == 1
script = script[:script.index(a)] + """  var MIR = null, RUN = null;
  var TX = {}, SEED = [], RH = [], TS = {}, MT = {};

""" + script[script.index(b):]

a = '  document.getElementById("prov").textContent ='
b = "  var TOOLKEY = ["
assert script.count(a) == 1 and script.count(b) == 1
script = script[:script.index(a)] + script[script.index(b):]

a = '  document.getElementById("tkbody").innerHTML = TOOLKEY.map(function(t){'
b = "  /* ---------- map ---------- */"
assert script.count(a) == 1 and script.count(b) == 1
script = script[:script.index(a)] + script[script.index(b):]

a = "  var GENES = Object.keys(TX);\n  var sel = \"PDCD4\", selSite = null, show6 = false, sortby = \"seed\";\n"
assert script.count(a) == 1
script = script.replace(a, "  var GENES = [];\n  var sel = null, selSite = null, show6 = false;\n")

# P_CT can be absent even when a conserved site is counted
a = 'ts[2].toFixed(2)'
assert script.count(a) == 1
script = script.replace(a, '(ts[2]==null?"not reported":ts[2].toFixed(2))')

# a tool that was never selected must read "not run", not "—"
a, b = "  function geneRow(g){", "  function detailRow(g){"
assert script.count(a) == 1 and script.count(b) == 1
script = script[:script.index(a)] + '''  function ran(t){ return RAN[t] === true; }

  function geneRow(g){
    var s = bestSeed(g), r = bestRh(g), ts = TS[g], mt = MT[g];
    var regions = {}; seedOf(g).forEach(function(x){ regions[x[1]] = 1; });
    var regList = Object.keys(regions).sort(function(a, b){
      return ["5UTR","CDS","3UTR"].indexOf(a) - ["5UTR","CDS","3UTR"].indexOf(b); });
    var nSeed = seedOf(g).length, nRh = rhOf(g).length;
    var seedEmpty = ran("seed") ? none() : nrun();

    var cells = [];
    cells.push('<td><span class="gene">' + g + '</span><span class="txid">' +
               TX[g].rs + "</span></td>");
    cells.push("<td>" + (regList.length
      ? regList.map(function(x){ return '<span class="region ' + RC[x] + '">' +
          RL[x] + "</span>"; }).join("")
      : seedEmpty) + "</td>");
    cells.push('<td class="colsep">' + (s
      ? '<span class="site ' + SITE_CLASS[s[2]] + '">' + s[2] + "</span>" +
        (nSeed > 1 ? '<span class="sub2">' + nSeed + " sites total</span>" : "")
      : seedEmpty) + "</td>");
    cells.push('<td class="num">' + (s
      ? s[3].toLocaleString() + "–" + s[4].toLocaleString() +
        '<span class="sub2">' + RL[s[1]] + "</span>"
      : seedEmpty) + "</td>");
    cells.push('<td class="num colsep">' + (r
      ? r[4].toFixed(1) + meter(Math.abs(r[4]) / 35) +
        (nRh > 1 ? '<span class="say">best&nbsp;of&nbsp;' + nRh + " foldings</span>" : "")
      : (ran("rnahybrid") ? none() : nrun())) + "</td>");

    var has3 = SEED.some(function(x){ return x[0] === g && x[1] === "3UTR"; }) ||
               RH.some(function(x){ return x[0] === g && x[1] === "3UTR"; });
    var tsEmpty = !ran("targetscan") ? nrun() : (has3 ? none() : ncov());
    cells.push('<td class="num colsep">' + (ts
      ? ts[0].toFixed(3) + meter(Math.abs(ts[0]), true)
      : tsEmpty) + "</td>");
    cells.push("<td>" + (ts
      ? (ts[1] > 0
          ? '<span class="chip cons" title="' + ts[1] + " conserved site" +
            (ts[1] === 1 ? "" : "s") +
            ' counted by TargetScan for this gene">Conserved</span>' +
            '<span class="say">P<sub>CT</sub> ' +
            (ts[2] == null ? "not reported" : ts[2].toFixed(2)) + "</span>"
          : '<span class="chip noncons">Not conserved</span>' +
            '<span class="say">P<sub>CT</sub> not applicable</span>')
      : tsEmpty) + "</td>");
    cells.push('<td class="colsep">' + (mt
      ? '<span class="chip ' + MTC[mt.t][0] + '">' + MTC[mt.t][1] + "</span>" +
        '<span class="say">' + mtSay(mt) + "</span>" +
        (mt.snf + mt.wnf > 0 ? '<span class="warnline">' + (mt.snf + mt.wnf) +
          " experiment" + (mt.snf + mt.wnf === 1 ? "" : "s") +
          " reported no effect</span>" : "")
      : (ran("mirtarbase")
          ? none() + '<span class="say">Not reported in miRTarBase</span>'
          : nrun())) + "</td>");
    cells.push('<td class="colsep">' + nbuilt() + "</td>");
    return '<tr class="generow' + (sel === g ? " sel" : "") + '" data-g="' + g +
           '">' + cells.join("") + "</tr>";
  }

''' + script[script.index(b):]

# cut the old wiring; ours replaces it
a = '  document.getElementById("show6").addEventListener'
assert script.count(a) == 1
script = script[:script.index(a)]

# A gene row expands on click but never closed again: clicking the open row
# was a no-op. Make it a toggle, and let the binding map cope with nothing
# being selected - it reads TX[sel] on the first line and would otherwise
# throw the moment a row is closed.
a = """        if (sel !== tr.dataset.g) { sel = tr.dataset.g; selSite = null; }
        render();"""
assert script.count(a) == 1
script = script.replace(a, """        sel = (sel === tr.dataset.g) ? null : tr.dataset.g;
        selSite = null;
        render();""")

a = """  function renderMap(){
    var t = TX[sel],"""
assert script.count(a) == 1
script = script.replace(a, """  function renderMap(){
    if (!sel || !TX[sel]){
      // Closing the open row leaves nothing to draw. Say so, rather than
      // hiding the panel - a section that vanishes reads as a broken page.
      document.getElementById("map").innerHTML =
        '<p class="say mapnone">Select a gene in the table below to draw ' +
        'its binding map.</p>';
      document.getElementById("maphint").textContent = "";
      return;
    }
    var t = TX[sel],""")

EXTRA_CSS = """
  [hidden]{display:none!important}
  .qform{display:flex;flex-wrap:wrap;gap:14px 18px;align-items:flex-end}
  .qform label.f{display:flex;flex-direction:column;gap:4px;font-size:12.5px;color:var(--muted)}
  .qform label.f span{font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint)}
  .qform input[type=text]{font:inherit;font-size:13.5px;padding:7px 10px;border:1px solid var(--line);border-radius:4px;background:var(--paper);color:var(--ink);min-width:230px}
  .qform input[type=text]:focus{outline:2px solid var(--accent);outline-offset:-1px}
  .qform .slow{font-style:normal;color:var(--warn);font-size:11px}
  .go{appearance:none;border:1px solid var(--accent);background:var(--accent);color:var(--accent-ink);font:inherit;font-weight:600;font-size:13.5px;padding:8px 20px;border-radius:4px;cursor:pointer}
  .go[disabled]{opacity:.5;cursor:default}
  .notice.err{background:var(--sel-wash);border-color:var(--sel);color:var(--sel);display:block;margin-top:11px}
  .linkbtn{appearance:none;background:none;border:none;padding:0;font:inherit;font-size:11.5px;color:var(--accent);border-bottom:1px dotted var(--accent);cursor:pointer}
  .linkbtn[disabled]{color:var(--faint);border-bottom-color:transparent;cursor:default}
  .pager{display:flex;align-items:center;gap:10px;margin-left:auto}
  .pager span{font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:11px;color:var(--muted)}
  .runwait td{color:var(--faint)}
  .gsgrid{display:flex;flex-direction:column;gap:9px}
  .gsrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:13px}
  .gsrow>label.tick{display:inline-flex;align-items:center;gap:6px;min-width:176px;cursor:pointer}
  .gsrow input[type=checkbox]{accent-color:var(--accent);width:15px;height:15px}
  .gsrow select,.gsrow input[type=number]{font:inherit;font-size:12.5px;padding:4px 7px;border:1px solid var(--line);border-radius:4px;background:var(--paper);color:var(--ink)}
  .gsrow input[type=number]{width:82px;font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace}
  .gsrow[data-off="1"]{opacity:.45}
  .gsnote{font-size:11px;color:var(--faint)}
  .gsbar{display:flex;flex-direction:column;gap:7px;margin-top:12px;padding-top:11px;border-top:1px solid var(--line-soft)}
  .gsfoot{display:flex;align-items:center;gap:14px;margin-top:13px;padding-top:12px;border-top:1px solid var(--line-soft)}
  .gsfoot .say{max-width:none;margin:0;flex:1}
  #gscount{font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;text-transform:none;letter-spacing:0}
  #gscount.ok{color:var(--ok)}
  #gscount.warn{color:var(--warn)}
  #enrichhead{font-size:13px;line-height:1.55;color:var(--ink);margin:0 0 4px}
  #enrichmeta{font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:10.5px;color:var(--faint);letter-spacing:.02em;margin:0 0 14px}
  .tabs{display:flex;gap:2px;margin:0 0 12px;border-bottom:1px solid var(--line)}
  .tabs button{appearance:none;background:none;border:none;border-bottom:2px solid transparent;font:inherit;font-size:12.5px;color:var(--muted);padding:6px 12px;cursor:pointer;margin-bottom:-1px}
  .tabs button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}
  .tabs button b{font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:10.5px;font-weight:400;color:var(--faint);margin-left:5px}
  .terms{width:100%;border-collapse:collapse;font-size:13px}
  .terms th{text-align:left;font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint);font-weight:500;padding:0 10px 6px 0;border-bottom:1px solid var(--line)}
  .terms td{padding:7px 10px 7px 0;border-bottom:1px solid var(--line-soft);vertical-align:top}
  .terms tr.t{cursor:pointer}
  .terms tr.t:hover>td{background:var(--surface-2)}
  .terms .num{font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:12px;white-space:nowrap}
  .terms .tid{font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:10.5px;color:var(--faint);display:block}
  .terms .caret{color:var(--faint);font-size:9px;width:12px}
  .terms tr.x>td{padding:0 10px 11px 0;border-bottom:1px solid var(--line-soft)}
  .terms .chips{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 7px}
  .terms .chips button{appearance:none;background:var(--accent-wash);border:1px solid var(--line-soft);border-radius:3px;font:inherit;font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:11px;color:var(--accent);padding:2px 6px;cursor:pointer}
  .terms dl.four{display:grid;grid-template-columns:auto auto;gap:3px 14px;justify-content:start;margin:0;font-size:11.5px;color:var(--muted);line-height:1.6}
  .terms dl.four dt{margin:0}
  .terms dl.four dt i{font-style:normal;font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;color:var(--faint)}
  .terms dl.four dd{margin:0;font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;color:var(--ink);text-align:right}
  .terms .four code{font-family:inherit;font-size:11px;color:var(--ink)}
  .tabs{flex-wrap:wrap}
  .mapnone{margin:0;padding:26px 2px;color:var(--faint)}
  .tsearch{margin:0 0 12px}
  .tsearch label{display:block;font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint);margin-bottom:5px}
  .tsbox{position:relative;max-width:420px}
  .tsbox input{width:100%;font:inherit;font-size:13px;padding:7px 28px 7px 10px;border:1px solid var(--line);border-radius:4px;background:var(--paper);color:var(--ink);box-sizing:border-box}
  .tsbox input:focus{outline:2px solid var(--accent);outline-offset:-1px}
  .tsbox input::-webkit-search-cancel-button{display:none}
  .tsbox button{position:absolute;right:6px;top:50%;transform:translateY(-50%);appearance:none;background:none;border:none;font-size:16px;line-height:1;color:var(--faint);cursor:pointer;padding:2px 4px}
  .tsbox button:hover{color:var(--ink)}
  .termfoot{display:flex;align-items:center;gap:12px;margin-top:11px;font-size:11.5px;color:var(--faint)}
  .sub2line{margin:0;font-size:16px;font-weight:600;color:var(--accent);letter-spacing:-.005em}
  .sources{margin:6px 0 0;font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;font-size:10.5px;color:var(--faint);letter-spacing:.02em}
"""

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>miRNA target tool</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>%s%s</style>
</head>
<body>

<div class="wrap">

  <header class="masthead">
    <div class="kicker" id="kicker"></div>
    <h1 id="title">&nbsp;</h1>
    <p class="sub2line" id="subtitle"></p>
    <p class="sub" id="tagline"></p>
  </header>

  <section class="panel" id="querybox">
    <h2>New search<em></em></h2>
    <div class="panel-body">
      <form class="qform" id="qform">
        <label class="f"><span>miRNA</span>
          <input type="text" id="f_mirna" placeholder="hsa-miR-21-5p or MIMAT0000076" autocomplete="off"></label>
        <label class="f"><span>Genes (optional)</span>
          <input type="text" id="f_genes" placeholder="empty = whole transcriptome" autocomplete="off"></label>
        <div class="fgroup" id="f_tools"><span>Tools</span></div>
        <button class="go" id="runbtn" type="submit">Run</button>
      </form>
      <div class="notice err" id="qerr" hidden></div>
    </div>
  </section>

  <section class="panel" id="runbox" hidden>
    <h2>Running<em id="runjob"></em></h2>
    <div class="panel-body" id="runlist"></div>
  </section>

  <div id="results" hidden>

    <div class="notice" id="prov"></div>
""" % (style, EXTRA_CSS)

TAIL_JS = r"""
  /* ================== live data ================== */

  function el(id){ return document.getElementById(id); }

  function jsonOrThrow(r){
    return r.json().then(function(b){
      if (!r.ok) throw (b && b.detail) ? b.detail : b;
      return b;
    });
  }
  function api(path){ return fetch(path).then(jsonOrThrow); }
  function post(path, body){
    return fetch(path, {method: "POST", headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(body)}).then(jsonOrThrow);
  }

  var TOOLMETA = {}, MIRINFO = null, JOBID = null, JOBST = null, POLL = null;
  var RAN = {};
  var PAGE = {limit: 25, offset: 0, sort: "seed", total: 0};
  var SORTMAP = {seed: "seed", ts: "targetscan", rh: "rnahybrid", mt: "mirtarbase"};

  /* the server chose the gene order; do not re-sort the page */
  function order(){ return GENES.slice(); }

  function revcomp(s){
    var m = {A: "T", T: "A", G: "C", C: "G", U: "A"};
    return String(s).toUpperCase().split("").reverse().map(function(c){
      return m[c] || c; }).join("");
  }
  function markSeed(seq){
    if (!seq || seq.length < 8) return seq || "";
    return seq[0] + "<mark>" + seq.slice(1, 8) + "</mark>" + seq.slice(8);
  }

  var ERRTEXT = {
    mirna_not_found: "No miRNA matches that name. Check the spelling, or paste a " +
                     "MIMAT accession such as MIMAT0000076.",
    mirna_ambiguous: "That name has meant different miRNAs in different miRBase " +
                     "releases, so it cannot be resolved on its own.",
    gene_not_found: "A gene in that list was not recognised.",
    no_mane_transcript: "That gene has no MANE Select transcript, so there is " +
                        "nothing to scan.",
    job_not_found: "That job no longer exists."
  };
  function showErr(e){
    var code = e && e.error;
    var msg = (e && e.message) ? e.message
            : (code && ERRTEXT[code]) ? ERRTEXT[code]
            : (code || String(e));
    if (e && e.query) msg += "  (you typed: " + e.query + ")";
    if (e && e.candidates && e.candidates.length)
      msg += " — candidates: " + e.candidates.join(", ");
    var box = el("qerr");
    box.textContent = msg;
    box.hidden = false;
    el("runbtn").disabled = false;
  }

  /* ---------- the tool key, versions from /tools ---------- */
  function toolkey(){
    el("tkbody").innerHTML = TOOLKEY.map(function(t){
      return '<tr' + (t[6] ? ' class="pending"' : "") + '><td><span class="tname">' +
        t[0] + '<span class="tver">' + t[1] + "</span></span></td><td>" + t[2] +
        '</td><td class="unit">' + t[3] + "</td><td>" + t[4] + "</td><td>" + t[5] +
        "</td></tr>";
    }).join("");
  }

  /* ---------- panels ---------- */
  function runTable(){
    var by = {};
    (JOBST.tools || []).forEach(function(t){ by[t.tool] = t; });
    var rows = Object.keys(TOOLMETA).sort().map(function(n){
      var t = by[n], v = TOOLMETA[n].version;
      if (!t)
        return '<tr class="pending"><td>' + n + "</td><td>" + v +
               '</td><td class="n">not run</td><td class="n">—</td><td class="n">—</td></tr>';
      return "<tr><td>" + n + "</td><td>" + v + '</td><td class="n">' +
        t.n_results.toLocaleString() + '</td><td class="n">' +
        (t.n_genes == null ? "—" : t.n_genes.toLocaleString()) + '</td><td class="n">' +
        (t.seconds == null ? "—" : t.seconds.toFixed(2)) + "</td></tr>";
    });
    rows.push('<tr class="pending"><td>ml model</td><td>not built</td>' +
              '<td class="n">—</td><td class="n">—</td><td class="n">—</td></tr>');
    return '<table class="runs"><thead><tr><th>Tool</th><th>Version</th>' +
      '<th class="n">Records</th><th class="n">Genes</th><th class="n">Seconds</th>' +
      "</tr></thead><tbody>" + rows.join("") + "</tbody></table>";
  }

  function fillPanels(){
    el("prov").textContent =
      RUN.job + " · " + RUN.date + " · " + RUN.results.toLocaleString() +
      " records · " + PAGE.total.toLocaleString() + " genes with a result · showing " +
      GENES.length;

    var scanned = (JOBST.params.genes && JOBST.params.genes.length)
      ? JOBST.params.genes.length + " gene" + (JOBST.params.genes.length === 1 ? "" : "s")
      : "every MANE Select transcript (one per gene)";

    el("qpanel").innerHTML = facts([
      ["miRNA", MIR ? MIR.name : JOBST.params.mirna_name],
      ["accession", MIR ? MIR.acc : JOBST.params.mirna_acc],
      ["mature", MIR && MIR.seq ? '<span class="seq">' + markSeed(MIR.seq) + "</span>" : none()],
      ["seed 2–8", MIR && MIR.seed
        ? '<span class="seq">' + MIR.seed + '</span> — site <span class="seq">' +
          revcomp(MIR.seed) + "</span>"
        : none()],
      ["TargetScan family", MIR && MIR.family
        ? MIR.family + " · conservation " + MIR.cons
        : '<span class="empty ncov">not in TargetScan v8.0</span>'],
      ["-"],
      ["transcripts scanned", scanned],
      ["regions", "5′UTR · CDS · 3′UTR"]
    ]);
    el("rpanel").innerHTML = runTable();
    el("runid").textContent = RUN.job;
    el("qscope").textContent = (JOBST.params.genes && JOBST.params.genes.length)
      ? "selected genes" : "whole transcriptome";
  }

  /* ---------- turn API rows into what the renderers expect ---------- */
  function applyData(p){
    TX = {}; SEED = []; RH = []; TS = {}; MT = {}; GENES = [];
    p.genes.forEach(function(g){
      var cds = null;
      g.regions.forEach(function(r){ if (r.region === "CDS") cds = [r.start, r.end]; });
      TX[g.symbol] = {rs: g.refseq, len: g.length, cds: cds || [1, g.length]};
      GENES.push(g.symbol);
    });
    p.results.forEach(function(r){
      if (r.tool === "seed")
        SEED.push([r.symbol, r.region, r.site_type, r.pos_start, r.pos_end]);
      else if (r.tool === "rnahybrid")
        RH.push([r.symbol, r.region, r.pos_start, r.pos_end, r.score]);
      else if (r.tool === "targetscan"){
        var e = r.extra || {};
        TS[r.symbol] = [r.score, e.sites_conserved || 0,
                        e.aggregate_pct == null ? null : e.aggregate_pct];
      } else if (r.tool === "mirtarbase"){
        var x = r.extra || {};
        MT[r.symbol] = {t: x.status, sf: x.strong_functional || 0,
                        wf: x.weak_functional || 0, snf: x.strong_nonfunctional || 0,
                        wnf: x.weak_nonfunctional || 0, sites: x.curated_sites || 0,
                        pm: (x.pmids || []).length};
      }
    });
    MIR = MIRINFO ? {name: MIRINFO.name, acc: MIRINFO.accession, seq: MIRINFO.sequence,
                     seed: MIRINFO.seed,
                     family: MIRINFO.targetscan ? MIRINFO.targetscan.family : null,
                     cons: MIRINFO.targetscan ? MIRINFO.targetscan.conservation : null}
                 : null;
    RUN = {job: JOBST.job_id, date: (JOBST.created_at || "").slice(0, 10),
           results: JOBST.n_results};
    RAN = {};
    (JOBST.params.tools || []).forEach(function(t){ RAN[t] = true; });
    sel = GENES.length ? GENES[0] : null;
    selSite = null;
    fillPanels();
  }

  /* ---------- job lifecycle ---------- */
  function renderRun(st){
    var want = (st.params && st.params.tools) || [];
    var by = {};
    (st.tools || []).forEach(function(t){ by[t.tool] = t; });
    el("runjob").textContent = st.job_id + " · " + st.status;
    el("runlist").innerHTML =
      '<table class="runs"><thead><tr><th>Tool</th><th>Status</th>' +
      '<th class="n">Records</th><th class="n">Seconds</th></tr></thead><tbody>' +
      want.map(function(n){
        var t = by[n];
        if (!t) return '<tr class="runwait"><td>' + n + "</td><td>waiting</td>" +
                       '<td class="n">—</td><td class="n">—</td></tr>';
        return "<tr><td>" + n + "</td><td>" + t.status + '</td><td class="n">' +
          t.n_results.toLocaleString() + '</td><td class="n">' +
          (t.seconds == null ? "—" : t.seconds.toFixed(2)) + "</td></tr>";
      }).join("") + "</tbody></table>";
  }

  function tick(){
    api("/jobs/" + JOBID).then(function(st){
      JOBST = st;
      renderRun(st);
      if (st.status === "done" || st.status === "failed"){
        clearInterval(POLL); POLL = null;
        el("runbtn").disabled = false;
        if (st.status === "failed") return showErr({message: st.error || "job failed"});
        PAGE.offset = 0;
        loadPage();
      }
    }).catch(function(e){ clearInterval(POLL); POLL = null; showErr(e); });
  }

  function loadPage(){
    api("/jobs/" + JOBID + "/genes?sort=" + PAGE.sort + "&limit=" + PAGE.limit +
        "&offset=" + PAGE.offset +
        (PAGE.gene ? "&gene=" + encodeURIComponent(PAGE.gene) : ""))
      .then(function(p){
        PAGE.total = p.total_genes;
        applyData(p);
        el("results").hidden = false;
        el("runbox").hidden = true;
        render();
        pager();
        gsBoxes();
      }).catch(showErr);
  }

  function submit(e){
    e.preventDefault();
    var mir = el("f_mirna").value.trim();
    if (!mir) return;
    var genes = el("f_genes").value.split(/[\s,]+/).filter(Boolean);
    var tools = [].slice.call(document.querySelectorAll("#f_tools input:checked"))
                  .map(function(c){ return c.value; });
    el("qerr").hidden = true;
    el("runbtn").disabled = true;
    el("results").hidden = true;
    MIRINFO = null;
    api("/mirnas/" + encodeURIComponent(mir))
      .then(function(m){ MIRINFO = m; })
      .catch(function(){ /* the POST below reports the real error */ })
      .then(function(){
        return post("/jobs", {mirna: mir,
                              genes: genes.length ? genes : null,
                              tools: tools.length ? tools : null});
      })
      .then(function(job){
        JOBID = job.job_id;
        JOBST = job;
        el("runbox").hidden = false;
        renderRun(job);
        POLL = setInterval(tick, 2000);
      })
      .catch(showErr);
  }

  /* ---------- toolbar ---------- */
  function pager(){
    var lo = PAGE.offset + 1, hi = Math.min(PAGE.offset + PAGE.limit, PAGE.total);
    el("pagelbl").textContent = PAGE.gene
      ? PAGE.gene + " only"
      : (PAGE.total ? "genes " + lo + "–" + hi + " of " +
                      PAGE.total.toLocaleString() : "no genes");
    el("prevpg").disabled = PAGE.offset <= 0;
    el("nextpg").disabled = hi >= PAGE.total;
    // shown only while the table is filtered to one gene from a pathway term
    var back = el("ungene");
    back.hidden = !PAGE.gene;
    back.textContent = "← all genes";
  }

  function wire(){
    el("qform").addEventListener("submit", submit);

    el("show6").addEventListener("change", function(e){
      show6 = e.target.checked; selSite = null; render();
    });
    el("sortby").addEventListener("change", function(e){
      PAGE.sort = SORTMAP[e.target.value] || "gene";
      PAGE.offset = 0;
      if (JOBID) loadPage();
    });
    document.querySelectorAll("#regfilter input").forEach(function(cb){
      cb.addEventListener("change", function(){
        regOn[cb.value] = cb.checked; selSite = null; render();
      });
    });

    var bar = document.querySelector(".toolbar");
    var d = document.createElement("div");
    d.className = "pager";
    d.innerHTML = '<button class="linkbtn" id="ungene" type="button" hidden></button>' +
                  '<button class="linkbtn" id="prevpg" type="button">← previous</button>' +
                  '<span id="pagelbl"></span>' +
                  '<button class="linkbtn" id="nextpg" type="button">next →</button>';
    bar.appendChild(d);
    el("ungene").addEventListener("click", function(){
      PAGE.gene = null; PAGE.offset = 0; loadPage();
    });
    el("prevpg").addEventListener("click", function(){
      PAGE.offset = Math.max(0, PAGE.offset - PAGE.limit); loadPage();
    });
    el("nextpg").addEventListener("click", function(){
      PAGE.offset += PAGE.limit; loadPage();
    });
  }

  /* ---------- pathway analysis ---------- */
  var GSTIMER = null;

  function gsBoxes(){
    var rows = [];
    // TargetScan's conserved sites are the default list: measured on this
    // project's own data, an 8mer list gave no enrichment at all and adding
    // it to the conserved list was no better than a random subset of the
    // same size (manifests/pathway_design.md).
    var tsFirst = ran("targetscan");
    if (ran("seed")){
      var cats = (TOOLMETA["seed"] && TOOLMETA["seed"].categories) || ["8mer"];
      rows.push('<div class="gsrow" data-tool="seed"><label class="tick">' +
        '<input type="checkbox" id="gs_seed"' + (tsFirst ? "" : " checked") +
        '> Seed site</label>' +
        '<select id="gs_seed_v">' + cats.map(function(c, i){
          return '<option value="' + c + '"' + (i === 0 ? " selected" : "") + ">" +
                 c + (i ? " or better" : "") + "</option>";
        }).join("") + '<option value="any">any site</option></select>' +
        '<span class="gsnote">ranking comes from the tool itself</span></div>');
    }
    if (ran("targetscan"))
      rows.push('<div class="gsrow" data-tool="targetscan"><label class="tick">' +
        '<input type="checkbox" id="gs_ts" checked> TargetScan</label>' +
        '<select id="gs_ts_v"><option value="conserved">conserved site</option>' +
        '<option value="any">any score</option>' +
        '<option value="cut">context++ at most</option></select>' +
        '<input type="number" id="gs_ts_c" value="-0.30" step="0.05" hidden>' +
        '<span class="gsnote" id="gs_ts_n">TargetScan publishes no cutoff, so a ' +
        'number here is yours</span></div>');
    if (ran("rnahybrid"))
      rows.push('<div class="gsrow" data-tool="rnahybrid"><label class="tick">' +
        '<input type="checkbox" id="gs_rh"> RNAhybrid</label>' +
        "<span>\u0394G at most</span>" +
        '<input type="number" id="gs_rh_c" value="-25" step="1">' +
        '<span class="gsnote">kcal/mol \u00b7 measured from this run, editable</span></div>');
    if (ran("mirtarbase"))
      rows.push('<div class="gsrow" data-tool="mirtarbase"><label class="tick">' +
        '<input type="checkbox" id="gs_mt"> miRTarBase</label>' +
        '<span class="gsnote">genes with strong experimental support</span></div>');
    el("gsboxes").innerHTML = rows.join("");
    // gsBoxes() runs again on every page of the table, so this must not stack
    // listeners: two listeners would start two enrichment runs per click.
    if (!el("gsrun").dataset.wired){
      el("gsrun").addEventListener("click", gsRun);
      el("gsrun").dataset.wired = "1";
    }
    document.querySelectorAll("#enrich input, #enrich select").forEach(function(x){
      x.addEventListener("change", gsChanged);
      if (x.type === "number") x.addEventListener("input", gsChanged);
    });
    gsChanged();
  }

  function gsSpec(){
    // One reading of the boxes, used for both the live count (a query string)
    // and the run request (a JSON body). Two readings would be two chances to
    // count one thing and compute another.
    var o = {}, boxes = 0;
    if (el("gs_seed") && el("gs_seed").checked){
      o.seed = el("gs_seed_v").value; boxes++;
    }
    if (el("gs_ts") && el("gs_ts").checked){
      var v = el("gs_ts_v").value;
      o.targetscan = (v === "cut" ? el("gs_ts_c").value : v); boxes++;
    }
    if (el("gs_rh") && el("gs_rh").checked){
      o.rnahybrid = el("gs_rh_c").value; boxes++;
    }
    if (el("gs_mt") && el("gs_mt").checked){ o.mirtarbase = "strong"; boxes++; }
    var regs = [].slice.call(document.querySelectorAll("#gsregions input:checked"))
                 .map(function(c){ return c.value; });
    if (regs.length && regs.length < 3) o.regions = regs;
    var m = document.querySelector("#gsmatch input:checked");
    o.match = m ? m.value : "all";
    var q = Object.keys(o).map(function(k){
      var v = o[k];
      return k + "=" + encodeURIComponent(v instanceof Array ? v.join(",") : v);
    }).join("&");
    return {query: q, boxes: boxes, body: o};
  }

  function gsChanged(){
    if (el("gs_ts")) el("gs_ts_c").hidden = el("gs_ts_v").value !== "cut";
    document.querySelectorAll("#enrich .gsrow").forEach(function(r){
      var cb = r.querySelector("input[type=checkbox]");
      r.dataset.off = (cb && cb.checked) ? "0" : "1";
    });
    var spec = gsSpec();
    el("gsmatch").hidden = spec.boxes < 2;
    clearTimeout(GSTIMER);
    GSTIMER = setTimeout(function(){ gsCount(spec.query); }, 250);
  }

  function gsCount(query){
    if (!JOBID) return;
    api("/jobs/" + JOBID + "/geneset?" + query).then(function(r){
      var c = el("gscount");
      c.textContent = r.count.toLocaleString() + " genes selected";
      c.className = (r.count >= 200 && r.count <= 1500) ? "ok" : "warn";
      // A list outside 200-1500 is still allowed to run: the range is advice,
      // not a rule, and the 628-gene list finding nothing is a real result.
      el("gsrun").disabled = (r.count === 0);
      el("gssentence").textContent = r.count === 0
        ? "Tick at least one box."
        : r.sentence + (r.count < 200
            ? " \u2014 too few genes for enrichment to reach significance."
            : (r.count > 1500
               ? " \u2014 a list this large makes almost anything look enriched."
               : ""));
    }).catch(function(e){
      el("gscount").textContent = "\u2014";
      el("gscount").className = "warn";
      el("gsrun").disabled = true;
      el("gssentence").textContent = (e && e.message) || "the filter was refused";
    });
  }

  /* ---------- enrichment: run it, then read it ---------- */
  var ENR = null, ENRSRC = null, ENRLIMIT = 20, ENRPOLL = null;
  var ENRQ = "", QTIMER = null;

  // BP, CC and MF mean nothing to a reader who has not met them before, and a
  // tab is the worst place to make someone remember an abbreviation.
  var SRCNAME = {"GO:BP": "GO: Biological Process",
                 "GO:CC": "GO: Cellular Component",
                 "GO:MF": "GO: Molecular Function",
                 "KEGG": "KEGG"};

  function esc(s){
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function gsRun(){
    if (!JOBID) return;
    ENRSRC = null;
    el("gsrun").disabled = true;
    el("gsrun").textContent = "Starting\u2026";
    fetch("/jobs/" + JOBID + "/enrichment", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify(gsSpec().body)
    }).then(function(r){
      return r.json().then(function(j){
        if (!r.ok) throw new Error((j.detail && j.detail.message) ||
                                   "the request was refused");
        return j;
      });
    }).then(function(j){
      watchRun(j.run_id);
    }).catch(function(e){
      gsIdle();
      el("gssentence").textContent = e.message || "could not start";
    });
  }

  function gsIdle(){
    el("gsrun").disabled = false;
    el("gsrun").textContent = "Run GO and KEGG";
  }

  function fetchRun(runId){
    // While searching, every match is returned rather than a first page: a
    // hidden match is worse than a long list, and the search exists precisely
    // to reach terms below the top of the ranking.
    var lim = ENRQ ? 1000 : ENRLIMIT;
    return api("/enrichment/" + runId + "?limit=" + lim +
               (ENRSRC ? "&source=" + encodeURIComponent(ENRSRC) : "") +
               (ENRQ ? "&q=" + encodeURIComponent(ENRQ) : ""));
  }

  function wireSearch(){
    var box = el("termq");
    if (box.dataset.wired) return;
    box.dataset.wired = "1";
    box.addEventListener("input", function(){
      // The database does the searching, so this waits for a pause in typing
      // rather than asking on every keystroke.
      clearTimeout(QTIMER);
      QTIMER = setTimeout(function(){
        ENRQ = box.value.trim();
        el("termqx").hidden = !ENRQ;
        if (ENR) fetchRun(ENR.run.run_id).then(function(r){
          ENR = r; renderEnrich();
        });
      }, 200);
    });
    el("termqx").addEventListener("click", function(){
      box.value = ""; ENRQ = ""; el("termqx").hidden = true;
      if (ENR) fetchRun(ENR.run.run_id).then(function(r){
        ENR = r; renderEnrich();
      });
      box.focus();
    });
  }

  function watchRun(runId){
    clearTimeout(ENRPOLL);
    el("enrichout").hidden = false;
    el("enrichstate").textContent = "starting";
    (function poll(){
      fetchRun(runId).then(function(r){
        ENR = r;
        // The first answer is the only one that knows which ontologies came
        // back, so the opening tab can only be chosen once it has arrived.
        // Ask again for that tab, then carry on - the status handling below
        // must run either way, or the button never comes back.
        var srcs = Object.keys(r.terms_by_source || {});
        if (!ENRSRC && srcs.length){
          ENRSRC = srcs[0];
          return fetchRun(runId).then(function(r2){ ENR = r2; });
        }
      }).then(function(){
        renderEnrich();
        var st = ENR.run.status;
        if (st === "queued" || st === "running"){
          el("gsrun").textContent = st === "queued" ? "Queued\u2026" : "Running\u2026";
          ENRPOLL = setTimeout(poll, 2000);
        } else {
          gsIdle();
        }
      }).catch(function(){
        el("enrichstate").textContent = "could not be read";
        gsIdle();
      });
    })();
  }

  function renderEnrich(){
    var run = ENR.run;
    el("enrichstate").textContent =
      run.status === "done"
        ? (run.n_terms === 0 ? "no enriched terms" : run.n_terms + " terms")
        : (run.status === "failed" ? "failed" : run.status + "\u2026");

    // Two sentences, because one would be wrong. 19,363 is the background we
    // selected from; it is not the denominator of any single test. Each
    // ontology annotates a different part of it - 17,116 for GO:BP against
    // 8,516 for KEGG - so the number that actually divides changes per tab.
    el("enrichhead").textContent = run.rule_sentence +
      " were tested against a MANE Select background of " +
      run.n_background.toLocaleString() + " genes. Each ontology was tested " +
      "against the part of that background it annotates, so the denominator " +
      "differs between tabs.";

    var bits = [run.background_source + " " + run.background_version];
    if (run.clusterprofiler_version)
      bits.push("clusterProfiler " + run.clusterprofiler_version);
    if (run.orgdb_version) bits.push("org.Hs.eg.db " + run.orgdb_version);
    bits.push((run.p_adjust_method === "BH" ? "Benjamini\u2013Hochberg"
                                            : run.p_adjust_method) +
              ", adjusted p < " + run.p_cutoff);
    if (run.n_genes_annotated != null && run.n_genes_annotated !== run.n_genes)
      bits.push(run.n_genes_annotated + " of " + run.n_genes +
                " genes known to the annotation");
    if (run.kegg_ok === 0) bits.push("KEGG unavailable, GO only");
    else if (run.kegg_fetched_at)
      bits.push("KEGG fetched " + run.kegg_fetched_at.replace("T", " "));
    if (run.stale) bits.push("the job has been re-run since this result");
    el("enrichmeta").textContent = bits.join("  \u00b7  ");

    if (run.status === "failed"){
      el("enrichtabs").innerHTML = "";
      el("termbody").innerHTML = '<tr><td colspan="4">' +
        esc(run.error || "the run failed") + "</td></tr>";
      el("termcount").textContent = "";
      el("termmore").hidden = true;
      return;
    }

    var counts = ENR.terms_by_source || {};
    var srcs = Object.keys(counts);
    // No "all sources" tab on purpose. GO and KEGG are tested against
    // different universes - 17,116 genes for GO:BP against 8,516 for KEGG -
    // so putting their p-values in one ranked list would invite a comparison
    // that is not valid.
    el("enrichtabs").innerHTML = srcs.map(function(s){
      return '<button type="button" data-src="' + esc(s) + '"' +
             (ENRSRC === s ? ' aria-selected="true"' : "") + ">" +
             esc(SRCNAME[s] || s) + "<b>" + counts[s] + "</b></button>";
    }).join("");
    el("enrichtabs").querySelectorAll("button").forEach(function(b){
      b.addEventListener("click", function(){
        ENRSRC = b.dataset.src;
        ENRLIMIT = 20;
        fetchRun(run.run_id).then(function(r){ ENR = r; renderEnrich(); });
      });
    });

    wireSearch();
    var rows = ENR.terms || [];
    el("termbody").innerHTML = rows.length ? rows.map(function(t, i){
      return '<tr class="t" data-i="' + i + '">' +
        '<td class="caret">\u25b8</td>' +
        "<td>" + esc(t.description) +
        '<span class="tid">' + esc(t.term_id) + "</span></td>" +
        '<td class="num">' + t.k_in_term_and_list +
        (t.k_in_term_and_list === 1 ? " gene" : " genes") + "</td>" +
        '<td class="num">' + t.p_adjust.toExponential(1) + "</td></tr>";
    }).join("") : ('<tr><td colspan="4">' + (run.status !== "done"
        ? "waiting for the worker\u2026"
        : (ENRQ
           ? "No term in " + esc(SRCNAME[ENRSRC] || ENRSRC) + " matches \u201c" +
             esc(ENRQ) + "\u201d."
           : "No term reached an adjusted p below " + run.p_cutoff +
             ". With " + run.n_genes + " genes all recognised by the " +
             "annotation, that is a result about the gene list, not a " +
             "lookup failure.")) + "</td></tr>");

    el("termbody").querySelectorAll("tr.t").forEach(function(tr){
      tr.addEventListener("click", function(){ toggleTerm(tr); });
    });

    var shown = rows.length, total = ENR.total, inSrc = ENR.in_source || 0;
    // The search box is only meaningful once there is something to search.
    document.querySelector(".tsearch").hidden = !(run.status === "done" && inSrc);
    el("termcount").textContent = !inSrc ? ""
      : (ENRQ
         ? ("showing " + total + " of " + inSrc + " terms matching \u201c" +
            ENRQ + "\u201d")
         : ("showing " + shown + " of " + inSrc + " in " +
            (SRCNAME[ENRSRC] || ENRSRC || "all")));
    el("termmore").hidden = !!ENRQ || shown >= total;
    el("termmore").textContent = "show all " + total + " \u2192";
    el("termmore").onclick = function(){
      ENRLIMIT = 500;
      fetchRun(run.run_id).then(function(r){ ENR = r; renderEnrich(); });
    };
  }

  function toggleTerm(tr){
    var next = tr.nextElementSibling;
    if (next && next.classList.contains("x")){
      next.remove();
      tr.querySelector(".caret").textContent = "\u25b8";
      return;
    }
    var t = ENR.terms[+tr.dataset.i];
    var chips = t.genes.split("/").map(function(g){
      return '<button type="button" data-g="' + esc(g) + '">' + esc(g) + "</button>";
    }).join("");
    var x = document.createElement("tr");
    x.className = "x";
    // The four integers, each one named. Anyone can put them into a
    // hypergeometric test and get the p-value below back out - which is the
    // whole reason they are stored per term rather than per run.
    function stat(label, value){
      return "<dt>" + label + "</dt><dd>" + value + "</dd>";
    }
    x.innerHTML = '<td></td><td colspan="3"><div class="chips">' + chips +
      '</div><dl class="four">' +
      stat("Your genes in this term <i>(k)</i>", t.k_in_term_and_list) +
      stat("Your genes this ontology annotates <i>(n)</i>",
           t.n_in_list.toLocaleString()) +
      stat("Background genes in this term <i>(K)</i>",
           t.k_in_term_and_background.toLocaleString()) +
      stat("Background genes it annotates <i>(N)</i>",
           t.n_in_background.toLocaleString()) +
      stat("p-value", "<code>" + t.p_value.toExponential(2) + "</code>") +
      stat("Adjusted p (" + ENR.run.p_adjust_method + ")",
           "<code>" + t.p_adjust.toExponential(2) + "</code>") +
      "</dl></td>";
    x.querySelectorAll("button").forEach(function(b){
      b.addEventListener("click", function(ev){
        ev.stopPropagation();
        focusGene(b.dataset.g);
      });
    });
    tr.parentNode.insertBefore(x, tr.nextSibling);
    tr.querySelector(".caret").textContent = "\u25be";
  }

  function focusGene(sym){
    PAGE.gene = sym;
    PAGE.offset = 0;
    loadPage();
    el("results").scrollIntoView({behavior: "smooth", block: "start"});
  }

  function boot(){
    wire();
    Promise.all([api("/about"), api("/tools")]).then(function(r){
      var about = r[0], tools = r[1].tools;
      document.title = about.name;
      el("title").textContent = about.name;
      el("tagline").textContent = about.description;
      el("subtitle").textContent = about.subtitle || "";
      var seen = {}, parts = [];
      (about.data_sources || []).forEach(function(s){
        if (/^miRBase_mature_(20|21|22)$/.test(s.name)) return;
        var label = /^miRBase/i.test(s.name) ? "miRBase " + s.version
                  : /^targetscan/i.test(s.name) ? "TargetScan " + s.version
                  : /^mirtarbase/i.test(s.name) ? "miRTarBase " + s.version
                  : s.name + " " + s.version;
        if (!seen[label]) { seen[label] = 1; parts.push(label); }
      });
      parts.push(about.name + " " + about.version);
      el("sources").textContent = "data " + parts.join("  ·  ");
      tools.forEach(function(t){ TOOLMETA[t.name] = t; });

      el("f_tools").innerHTML = '<span>Tools</span>' + tools.map(function(t){
        return '<label><input type="checkbox" value="' + t.name + '"' +
          (t.slow ? "" : " checked") + "> " + t.name +
          "</label>";
      }).join("");

      var map = {"Seed analyser": "seed", "RNAhybrid": "rnahybrid",
                 "TargetScan": "targetscan", "miRTarBase": "mirtarbase"};
      TOOLKEY.forEach(function(row){
        var n = map[row[0]];
        if (n && TOOLMETA[n])
          row[1] = (row[0] === "Seed analyser" ? "ours, v" : "") + TOOLMETA[n].version;
      });
      toolkey();
    }).catch(showErr);
  }

  boot();
})();
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HEAD + keep + """  </div>

  <p class="sources" id="sources"></p>

</div>

<script>
""" + script + TAIL_JS + """</script>
</body>
</html>
""")
print("wrote", OUT, OUT.stat().st_size, "bytes")
