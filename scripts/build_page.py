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
NOTE_SUBS.append((
 "The ΔG and context++ columns show the number and a bar on a stated scale, nothing else",
 "The ΔG and context++ columns show the number and nothing else"))

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
        <th></th><th>Term</th>
        <th class="sortable" data-sort="genes">Genes<span class="arrow"></span></th>
        <th class="sortable" data-sort="p">Adjusted p<span class="arrow"></span></th>
      </tr></thead><tbody id="termbody"></tbody></table>
      <div class="termfoot">
        <span id="termcount"></span>
        <button class="linkbtn" id="termmore" type="button" hidden></button>
        <button class="linkbtn expright" id="enrexp" type="button" hidden>Export terms (TSV) ↓</button>
        <button class="linkbtn" id="enrexpx" type="button" hidden>Excel ↓</button>
      </div>
    </div>
  </section>

  <section class="panel" id="netbox" hidden>
    <h2>Target network<em id="netstate"></em></h2>
    <div class="panel-body">
      <p class="say" id="nethead"></p>
      <div class="netbar">
        <label class="ctl">Genes
          <select id="netn">
            <option value="25">top 25</option>
            <option value="50" selected>top 50</option>
            <option value="100">top 100</option>
          </select>
        </label>
        <label class="ctl">Link genes sharing
          <select id="netmin">
            <option value="1" selected>1+ terms</option>
            <option value="2">2+ terms</option>
            <option value="3">3+ terms</option>
            <option value="5">5+ terms</option>
          </select>
        </label>
        <label class="switch"><input type="checkbox" id="netphys" checked>
          <span>Keep moving</span></label>
        <button class="linkbtn" id="netfit" type="button">Fit to view</button>
      </div>
      <div class="netcanvas" id="netcanvas"></div>
      <div class="netkey">
        <span><b id="k1"></b>miRNA</span>
        <span><b id="k2"></b>validated target (miRTarBase)</span>
        <span><b id="k3"></b>predicted only</span>
        <span><i></i>predicted or reported target — thicker = more tools agree</span>
        <span><i class="dash"></i>genes sharing enriched terms</span>
      </div>
      <div class="netinfo" id="netinfo"></div>
      <p class="netnote" id="netnote"></p>
    </div>
  </section>

  """ + keep[_notes:]

# The binding map draws whichever gene is selected in the table, so it belongs
# after the table rather than before it: meet the data, then the picture of one
# row of it.
_b0 = keep.index('<section class="panel browser">')
_b1 = keep.index("</section>", _b0) + len("</section>")
_map = keep[_b0:_b1]
keep = keep[:_b0] + keep[_b1:]
_tbl = keep.index('<div class="toolbar">')
keep = (keep[:_tbl] + _map +
        '\n\n  <h2 class="sectitle">The result table</h2>\n  ' + keep[_tbl:])

# The tool key is reference material, not a step in the workflow, so it moves
# down beside the notes that explain how to read the page.
_t0 = keep.index('<section class="toolkey">')
_t1 = keep.index("</section>", _t0) + len("</section>")
_tk = keep[_t0:_t1]
keep = keep[:_t0] + keep[_t1:]
_n = keep.index('<div class="notes">')
keep = keep[:_n] + _tk + "\n\n  " + keep[_n:]

# miRanda was dropped from the project, so its column comes out rather than
# standing there permanently reading "not built". An empty column for a tool
# that will never exist is worse than no column.
for _a, _b in [
    ('<th colspan="1" class="gsep">Not yet built</th>',
     '<th colspan="1" class="gsep">Not yet built</th>'),
    ('<span class="hn">ML model \u00b7 miRanda</span><span class="hu">later phases</span>',
     '<span class="hn">ML model</span><span class="hu">Phase 9</span>'),
    ('<span class="hu">kcal/mol \u00b7 bar 0 to \u221235</span>',
     '<span class="hu">kcal/mol</span>'),
    ('<span class="hu">bar 0 to \u22121</span>',
     '<span class="hu">site context score</span>'),
    ('<th colspan="2" class="gsep">Seed analyser \u2014 ours</th>',
     '<th colspan="2" class="gsep">Seed analyser</th>'),
    ]:
    assert keep.count(_a) == 1, _a[:50]
    keep = keep.replace(_a, _b)

a = '''    ["miRanda","not integrated",
     "A second, independent alignment-and-energy opinion",
     "an alignment score","Higher = better alignment. Useful mainly as a cross-check on the other two predictors.",
     "whole transcript",true]
  ];'''
assert script.count(a) == 1, "miRanda tool-key row"
script = script.replace(a, "  ];")

# The binding map lane captions and the detail-row paragraph explained the data
# model at length. The reader at that moment wants to know what the rows are,
# not how the tool is built.
for _a, _b in [
    ('<div class="lanecap">Seed sites <em>Watson\u2013Crick only</em></div>', ""),
    ('<div class="lanecap">RNAhybrid duplexes <em>span shown to scale \u00b7 '
     'G:U wobbles allowed</em></div>', "")]:
    assert script.count(_a) == 1, _a[:45]
    script = script.replace(_a, _b)

a = """    return '<div class="dethead">'+rows.length+" record"+(rows.length===1?"":"s")+" for "+g+
      ", one row each, exactly as stored \u2014 from the two tools that measure position."+
      (nAgree?" The Agreement column marks where both tools point at the same nucleotides.":"")+
      " TargetScan and miRTarBase report one value for the whole gene, so they have no row here.</div>"+"""
assert script.count(a) == 1, "dethead"
script = script.replace(a, """    return '<div class="dethead">miRNA binding sites identified in ' + g +
      "</div>"+""")

# The counts strip repeated what the table and the provenance line already say.
a = """    document.getElementById("rowcount").textContent =
      GENES.length+" genes · "+nSites+" seed sites · "+nDup+" duplexes"+
      (show6?"":" · 6mer sites hidden")+
      (off.length?" · "+off.join(" and ")+" hidden":"");"""
assert script.count(a) == 1, "rowcount"
# only the hidden-region note survives: it changes what the table shows.
script = script.replace(a, """    document.getElementById("rowcount").textContent =
      (off.length ? off.join(" and ") + " hidden" : "") +
      (show6 ? "" : (off.length ? " · " : "") + "6mer sites hidden");""")

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
        ""
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

# ---------------------------------------------------------------------------
# Redesign layer. Appended last so it wins on specificity ties.
#
# The approved layout was a set of cards on a tinted ground. This strips the
# card chrome and rebuilds the hierarchy out of type and space instead, which
# is how scientific software reads: section title, field label, column header,
# data - each one plainly a level below the last.
#
# Two colours survive because they carry information rather than decoration:
# the 5'UTR / CDS / 3'UTR region colours the binding map depends on, and the
# site-type banding that distinguishes an 8mer from a 6mer. Everything else
# goes to neutral ink on white.
REDESIGN_CSS = """
  /* ---- palette: white ground, darker secondary text ---- */
  :root, :root[data-theme="light"]{
    --paper:#ffffff; --surface:#ffffff; --surface-2:#f4f5f6; --surface-3:#fafbfb;
    --ink:#14181b; --muted:#454c52; --faint:#6a7278;
    --line:#d6dade; --line-soft:#e8eaec;
    --accent:#12507e; --accent-ink:#fff; --accent-wash:#eaf1f7;
    --blue:#12507e; --blue-wash:#eaf1f7;
    --ok:#1d6b48; --warn:#8a5a12; --sel:#a8410f; --sel-wash:#fbeee7;
  }
  @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
    --paper:#0e1113; --surface:#0e1113; --surface-2:#191d20; --surface-3:#14181a;
    --ink:#eef1f2; --muted:#b3bbc0; --faint:#8b959b;
    --line:#2c3236; --line-soft:#23282c;
    --accent:#68a8dd; --accent-ink:#0e1113; --accent-wash:#15242f;
    --blue:#68a8dd; --blue-wash:#15242f;
  }}
  body{font-family:'Inter','Source Sans 3',system-ui,-apple-system,
       BlinkMacSystemFont,sans-serif;font-size:14.5px;line-height:1.55;
       background:var(--paper)}

  /* ---- sections are headings and space, not boxes ---- */
  .wrap{max-width:1340px;padding:34px 26px 110px;gap:0}
  .panel, .toolkey, .toolbar, .notes, .panel.browser{
    background:none;border:0;border-radius:0;box-shadow:none;overflow:visible}
  .panel, .context, .toolkey, .notes, #results{margin:0 0 46px}
  .panel>h2, .browser>header h2, .notes h3{
    margin:0 0 4px;padding:0;background:none;border:0;
    font-family:inherit;font-size:20px;font-weight:700;letter-spacing:-.012em;
    text-transform:none;color:var(--ink);line-height:1.25}
  .panel>h2{display:flex;align-items:baseline;justify-content:space-between;
    gap:16px;flex-wrap:wrap;
    border-bottom:1px solid var(--line);padding-bottom:9px;margin-bottom:18px}
  .panel>h2 em{font-style:normal;font-size:13px;font-weight:400;
    color:var(--muted);letter-spacing:0;text-transform:none}
  .panel-body, .mapbody{padding:0}
  .browser>header{background:none;border:0;padding:0 0 9px;margin-bottom:18px;
    border-bottom:1px solid var(--line);align-items:baseline}
  .browser>header .hint{margin-left:auto;font-size:13px;color:var(--muted)}
  .browser>footer{border-top:1px solid var(--line-soft);padding:9px 0 0;
    font-size:12.5px;color:var(--muted)}
  .context{gap:46px;grid-template-columns:minmax(320px,1fr) minmax(340px,1.1fr)}
  @media (max-width:860px){.context{grid-template-columns:1fr;gap:0}}

  /* ---- field labels: readable, not faded ---- */
  .qform label.f span, .fgroup>span, .tsearch label, .gslabel,
  table.runs th, table.sites th, table.tk th, .terms th,
  table.results thead tr.grouprow th{
    font-family:inherit;font-size:12.5px;font-weight:600;letter-spacing:0;
    text-transform:none;color:var(--muted)}
  .qform label.f span{font-size:13px;color:var(--ink)}

  /* ---- tables: white, ruled, aligned ---- */
  table.results thead th, table.tk th{background:none}
  table.results thead tr.grouprow th{
    padding:0 10px 4px;font-size:11.5px;color:var(--faint);
    border-bottom:0;background:none}
  table.results thead tr:last-child th, table.tk th, .terms th,
  table.runs th, table.sites th{
    font-size:13px;font-weight:600;color:var(--ink);
    border-bottom:1px solid var(--line);padding-bottom:7px}
  table.results tbody td, table.tk td{font-size:13.5px;padding:9px 10px}
  table.runs td, table.sites td{font-size:13px}
  table.results tbody tr:hover>td{background:var(--surface-3)}
  .terms td{font-size:13.5px}

  /* ---- no decorative score bars: the number is the datum ---- */
  .meter{display:none!important}

  /* ---- controls ---- */
  .qform input[type=text], .tsbox input, .gsrow select,
  .gsrow input[type=number]{font-size:14px;border-color:var(--line);
    border-radius:3px;background:var(--surface)}
  .go{border-radius:3px;font-size:14px;padding:9px 22px}
  .gsrow>label.tick, .fgroup label{font-size:13.5px;color:var(--ink)}
  .gsnote, .say{color:var(--muted)}
  .tabs button{font-size:13.5px;padding:7px 14px}
  .tabs button b{font-size:12px}
  .notes ul{font-size:13.5px;color:var(--muted)}
  .notes{border-left:0;padding:0}
  .notes h3{border-bottom:1px solid var(--line);padding-bottom:9px;
    margin-bottom:18px}

  /* ---- numbered pagination ---- */
  .pager{gap:4px}
  .pgnum{appearance:none;background:none;border:1px solid transparent;
    border-radius:3px;font:inherit;font-size:13px;color:var(--muted);
    min-width:30px;padding:4px 7px;cursor:pointer;text-align:center}
  .pgnum:hover{background:var(--surface-2);color:var(--ink)}
  .pgnum[aria-current="true"]{border-color:var(--line);color:var(--ink);
    font-weight:600;background:var(--surface-2)}
  .pgnum[disabled]{color:var(--faint);cursor:default;background:none}
  .pggap{color:var(--faint);padding:0 2px;font-size:13px}
  .toolbar{padding:0;gap:12px 20px;margin-bottom:14px}
  .toolpick{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
    gap:7px 20px;margin-top:6px}
  label.tp{display:grid;grid-template-columns:auto 1fr;column-gap:8px;
    align-items:baseline;cursor:pointer}
  label.tp input{grid-row:1/3;align-self:center;accent-color:var(--accent);
    width:16px;height:16px}
  .tpn{font-size:14px;font-weight:600;color:var(--ink)}
  .tps{grid-column:2;font-size:12.5px;color:var(--muted);line-height:1.4}
  #f_tools{align-items:flex-start;flex-direction:column;gap:2px;flex:1 1 100%}
  #toolhint{color:var(--warn)}
  .gsearch{margin:0 0 10px}
  .gsearch .tsbox{max-width:460px}
  .terms dl.four dt i{color:var(--faint)}

  /* ---- column headers: the real ones, not the group labels ---- */
  .hcell{padding:7px 10px 8px;gap:2px}
  .hn{font-family:inherit;font-size:13.5px;font-weight:600;letter-spacing:0;
      text-transform:none;color:var(--ink)}
  .hu{font-family:inherit;font-size:12px;color:var(--muted);max-width:22ch;
      letter-spacing:0}
  table.results thead tr.grouprow th{font-size:12px;font-weight:600;
      color:var(--faint);text-transform:uppercase;letter-spacing:.06em}

  /* ---- provenance strip: information, not a status badge ---- */
  .notice{background:none;border:0;border-left:2px solid var(--line);
      border-radius:0;padding:2px 0 2px 11px;color:var(--muted);
      font-size:12.5px;margin-bottom:26px}
  .notice.err{background:var(--sel-wash);border:1px solid var(--sel);
      border-left-width:1px;border-radius:3px;padding:8px 12px;color:var(--sel)}

  /* ---- masthead ---- */
  .masthead{margin-bottom:46px}
  #title{font-size:30px;letter-spacing:-.02em}
  .sub2line{font-size:15.5px;color:var(--muted);font-weight:500}
  #tagline{max-width:74ch;color:var(--muted);font-size:14px}
  .sources{color:var(--faint)}

  /* ================= second pass ================= */

  /* ---- rules you can actually see ---- */
  :root, :root[data-theme="light"]{--line:#b9c0c6; --line-soft:#d5dade}
  table.results tbody td{border-bottom:1px solid var(--line-soft)}
  table.results thead tr:last-child th{border-bottom:2px solid var(--ink)}
  table.results thead th.colsep, table.results thead tr.grouprow th.gsep,
  table.results tbody td.colsep{border-left:1px solid var(--line)}
  table.runs th{border-bottom:2px solid var(--ink)}
  table.runs td{border-top:1px solid var(--line-soft)}
  .terms th{border-bottom:2px solid var(--ink)}
  .terms td{border-bottom:1px solid var(--line-soft)}

  /* ---- group headers: centred, real capitalisation, navy ---- */
  table.results thead tr.grouprow th{
    text-align:center;text-transform:none;letter-spacing:0;
    font-size:14px;font-weight:700;color:var(--accent);
    padding:9px 10px 7px}

  /* ---- numeric and short-token columns line up under their header ---- */
  table.results tbody td.num, table.results thead th.num{text-align:right}
  table.runs td.n, table.runs th.n{text-align:right}
  table.runs td, table.runs th{padding-right:22px}
  table.runs td:first-child{font-family:inherit;font-weight:500}

  /* ---- badges become text ---- */
  .site, .region, .chip{
    display:inline;background:none!important;border:0!important;
    padding:0;border-radius:0;font-family:inherit;font-weight:600;
    color:var(--ink);white-space:normal}
  .site{font-size:13.5px}
  .region{font-size:13px;margin-right:8px;font-weight:500}
  .site.s6{color:var(--muted);font-weight:500}
  .chip{font-weight:600}
  .chip.cons{color:var(--ok)} .chip.noncons{color:var(--muted)}
  .chip.val{color:var(--ok)} .chip.rep{color:var(--ink)}
  .chip.noeff{color:var(--sel)}
  .sub2{font-family:inherit;font-size:12px;color:var(--muted)}

  /* ---- selected row: blue, and still readable ---- */
  table.results tbody tr.generow.sel>td{
    background:#12507e;color:#fff;box-shadow:none;
    border-bottom-color:#12507e}
  tr.generow.sel .gene, tr.generow.sel .site, tr.generow.sel .region,
  tr.generow.sel .chip, tr.generow.sel .sub2, tr.generow.sel .txid,
  tr.generow.sel .say, tr.generow.sel td{color:#fff!important}
  tr.generow.sel .chip.cons, tr.generow.sel .chip.val{color:#bff0d4!important}
  table.results tbody tr.generow:hover>td{background:var(--surface-2)}
  table.results tbody tr.generow.sel:hover>td{background:#0f4470}

  /* ---- the toolbar above the table ---- */
  .toolbar{display:grid;grid-template-columns:1fr auto;gap:14px 26px;
    align-items:end;padding:0 0 12px;margin-bottom:0;
    border-bottom:1px solid var(--line)}
  .toolbar>label, .toolbar>.fgroup{display:flex;align-items:center;gap:8px;
    font-size:13.5px;color:var(--ink)}
  .toolbar select{font:inherit;font-size:13.5px;padding:6px 9px;
    border:1px solid var(--line);border-radius:3px;background:var(--surface);
    color:var(--ink)}
  #rowcount{grid-column:1/-1;font-size:12.5px;color:var(--muted)}
  .tbopts{display:flex;flex-wrap:wrap;align-items:center;gap:10px 24px}

  /* ---- pagination ---- */
  .pager{margin:16px 0 0;justify-content:space-between;width:100%;
    align-items:center}
  #pagelbl{font-family:inherit;font-size:13px;color:var(--muted)}
  #pgnums{display:flex;gap:3px;align-items:center}
  .pgnum{min-width:34px;padding:6px 9px;font-size:13.5px;
    border:1px solid var(--line-soft)}
  .pgnum[aria-current="true"]{background:var(--accent);color:#fff;
    border-color:var(--accent);font-weight:600}
  .pgnum[aria-current="true"]:hover{background:var(--accent);color:#fff}

  /* ---- sortable enrichment table ---- */
  .terms th.sortable{cursor:pointer;user-select:none;white-space:nowrap}
  .terms th.sortable:hover{color:var(--accent)}
  .terms th .arrow{font-size:10px;color:var(--faint);margin-left:5px}
  .terms th[aria-sort] .arrow{color:var(--accent)}
  .terms th[aria-sort]{color:var(--accent)}

  /* ---- nothing important is dimmed ---- */
  .txid, .hu, .gsnote, .say, .sub2, #rowcount, .termfoot{font-size:12.5px}
  .dethead{font-family:inherit;font-size:13.5px;font-weight:600;
    color:var(--ink);text-transform:none;letter-spacing:0;padding:12px 0 8px}
  .sectitle{margin:0 0 14px;font-size:20px;font-weight:700;
    letter-spacing:-.012em;color:var(--ink);
    border-bottom:1px solid var(--line);padding-bottom:9px}

  /* ---- badge text must inherit ink, not the old white-on-fill ---- */
  .site, .site.s8, .site.s7m8, .site.s7a1{color:var(--ink)!important}
  .region, .region.utr5, .region.cds, .region.utr3{color:var(--muted)!important}
  .empty{font-family:inherit;font-size:13px;color:var(--faint);font-style:normal}

  /* ---- everything inside a selected row stays legible ---- */
  tr.generow.sel td *, tr.generow.sel td{color:#fff!important}
  tr.generow.sel .empty{color:#c3d6e6!important}
  tr.generow.sel .chip.cons, tr.generow.sel .chip.val{color:#a9e7c4!important}
  tr.generow.sel sub{color:#fff!important}

  /* ---- the toolbar reads as one row of controls ---- */
  .toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px 26px;
    padding:0 0 12px;border-bottom:1px solid var(--line)}
  .toolbar>label{white-space:nowrap}
  #rowcount{margin-left:auto;font-size:12.5px;color:var(--muted)}
  .gsearch{margin:0 0 14px}
"""

# Export control. It sits at the right end of the table toolbar, with the
# other controls that decide what the table shows - because that is exactly
# what it exports.
EXPORT_CSS = """
  /* Export is an action, not a footnote, so it is a real button in the same
     type scale as the rest of the toolbar - not the .linkbtn hint style. It
     sits with the other controls rather than after the row count, which on a
     wrapping flex toolbar dropped it to a second line. #rowcount keeps its
     own margin-left:auto, so it stays pinned right exactly as designed. */
  .exp{position:relative;display:flex;align-items:center}
  .expbtn{appearance:none;font:inherit;font-size:13.5px;font-weight:600;
    padding:7px 17px;border:1px solid var(--accent);border-radius:4px;
    background:var(--surface);color:var(--accent);cursor:pointer;
    white-space:nowrap;line-height:1.25}
  .expbtn:hover{background:var(--accent);color:var(--accent-ink)}
  .expbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

  .expmenu{position:absolute;right:0;top:calc(100% + 8px);z-index:30;
    min-width:258px;padding:7px;background:var(--surface);
    border:1px solid var(--line);border-radius:6px;
    box-shadow:0 8px 26px rgba(0,0,0,.16)}
  .expnote{margin:7px 10px 4px;font-size:12px;line-height:1.5;
    color:var(--muted)}

  .exprow{display:flex;align-items:center;gap:6px;padding:4px 6px 4px 10px}
  .exprow>span{flex:1;font-size:13px;color:var(--ink)}
  .exprow>button{padding:5px 13px;border:1px solid var(--line);
    border-radius:4px;background:var(--surface);cursor:pointer;font:inherit;
    font-size:12.5px;font-weight:600;color:var(--accent)}
  .exprow>button:hover{background:var(--accent);color:var(--accent-ink);
    border-color:var(--accent)}

  .expsep{margin-top:6px;padding-top:8px;border-top:1px solid var(--line)}
  .expctl{display:flex;align-items:center;justify-content:space-between;
    gap:10px;padding:2px 10px 8px;font-size:13px;color:var(--ink)}
  .expctl select{font:inherit;font-size:13px;padding:4px 7px;
    border:1px solid var(--line);border-radius:3px;background:var(--surface);
    color:var(--ink)}
  .expsep>button{display:block;width:calc(100% - 20px);margin:0 10px;
    padding:7px 12px;border:1px solid var(--accent);border-radius:4px;
    background:var(--accent);color:var(--accent-ink);cursor:pointer;
    font:inherit;font-size:13px;font-weight:600}

  .expstat{margin-right:11px;font-size:13px;color:var(--muted);
    white-space:nowrap}
  .expstat a{color:var(--accent);font-weight:600;text-decoration:underline;
    text-underline-offset:2px}

  /* the enrichment panel's own exports, matched to the same scale */
  #enrexp, #enrexpx{font-size:12.5px;font-weight:600;padding:5px 13px;
    border:1px solid var(--line);border-radius:4px;background:var(--surface);
    color:var(--accent)}
  #enrexp:hover, #enrexpx:hover{background:var(--accent);
    color:var(--accent-ink);border-color:var(--accent)}
  .expright{margin-left:auto}
  #enrexpx{margin-left:7px}
"""

NETWORK_CSS = """
  .netbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px 20px;
    margin:0 0 12px;font-size:13px;color:var(--ink)}
  .netbar select{font:inherit;font-size:13px;padding:4px 8px;
    border:1px solid var(--line);border-radius:3px;background:var(--surface);
    color:var(--ink)}
  .netcanvas{height:520px;border:1px solid var(--line);border-radius:5px;
    background:var(--surface)}
  .netkey{display:flex;flex-wrap:wrap;gap:6px 18px;margin:10px 0 0;
    font-size:12px;color:var(--muted)}
  .netkey b{display:inline-block;width:11px;height:11px;border-radius:50%;
    margin-right:5px;vertical-align:-1px}
  .netkey i{display:inline-block;width:20px;height:0;margin-right:5px;
    vertical-align:4px;border-top:2px solid var(--muted)}
  .netkey i.dash{border-top-style:dotted}
  .netinfo{margin:12px 0 0;padding:12px 14px;border:1px solid var(--line);
    border-radius:5px;background:var(--surface-2);font-size:13px;
    line-height:1.6;min-height:54px}
  .netinfo h4{margin:0 0 5px;font-size:14px}
  .netinfo dl{display:grid;grid-template-columns:auto 1fr;gap:2px 14px;
    margin:6px 0 0}
  .netinfo dt{color:var(--muted);font-size:12px}
  .netinfo dd{margin:0;font-size:12.5px}
  .netnote{margin:9px 0 0;font-size:12px;color:var(--muted);line-height:1.55}
  /* the library's own 220 KB stylesheet is not vendored; this is the only
     rule its canvas tooltip actually needs */
  div.vis-tooltip{position:absolute;visibility:hidden;padding:6px 9px;
    white-space:normal;max-width:320px;font:12px/1.5 'Inter',system-ui,
    sans-serif;color:var(--ink);background:var(--surface);
    border:1px solid var(--line);border-radius:5px;
    box-shadow:0 4px 14px rgba(0,0,0,.14);pointer-events:none;z-index:60}
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
        <button class="go" id="runbtn" type="submit" disabled>Run</button>
        <span class="say" id="toolhint">Select at least one analysis method.</span>
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
""" % (style, EXTRA_CSS + REDESIGN_CSS + EXPORT_CSS + NETWORK_CSS)

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
  var PAGE = {limit: 10, offset: 0, sort: "seed", total: 0, q: ""};
  var GTIMER = null;
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
  var TOOLLABEL = {seed: "Seed analyser", rnahybrid: "RNAhybrid",
                   targetscan: "TargetScan", mirtarbase: "miRTarBase",
                   "ml model": "ML model"};
  function toolLabel(t){ return TOOLLABEL[String(t).toLowerCase()] || t; }

  function runTable(){
    var by = {};
    (JOBST.tools || []).forEach(function(t){ by[t.tool] = t; });
    var rows = Object.keys(TOOLMETA).sort().map(function(n){
      var t = by[n], v = TOOLMETA[n].version;
      if (!t)
        return '<tr class="pending"><td>' + toolLabel(n) + "</td><td>" + v +
               '</td><td class="n">not run</td><td class="n">—</td><td class="n">—</td></tr>';
      return "<tr><td>" + toolLabel(n) + "</td><td>" + v + '</td><td class="n">' +
        t.n_results.toLocaleString() + '</td><td class="n">' +
        (t.n_genes == null ? "—" : t.n_genes.toLocaleString()) + '</td><td class="n">' +
        (t.seconds == null ? "—" : t.seconds.toFixed(2)) + "</td></tr>";
    });
    rows.push('<tr class="pending"><td>ML model</td><td>not built</td>' +
              '<td class="n">—</td><td class="n">—</td><td class="n">—</td></tr>');
    return '<table class="runs"><thead><tr><th>Tool</th><th>Version</th>' +
      '<th class="n">Records</th><th class="n">Genes</th><th class="n">Seconds</th>' +
      "</tr></thead><tbody>" + rows.join("") + "</tbody></table>";
  }

  function fillPanels(){
    el("prov").textContent =
      RUN.job + " · " + RUN.date + " · " + RUN.results.toLocaleString() +
      " records · " + PAGE.total.toLocaleString() + " genes with a result";

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

  /* ---------- export ----------
     The file has to equal the screen. Region and 6mer are filtered in the
     browser, so the server is told about them explicitly here; if it were
     not, a user who had hidden 5'UTR and 6mer rows would still get them in
     the file, and would have no way to know. Anything still at its default
     is omitted, which keeps the URL short and readable. */
  function exportRegions(){
    return ["5UTR", "CDS", "3UTR"].filter(function(r){ return regOn[r]; });
  }

  function exportURL(scope, fmt){
    var u = "/jobs/" + JOBID + "/results." + (fmt === "xlsx" ? "xlsx" : "tsv");
    if (scope === "all") return u;
    var p = [], regs = exportRegions();
    // sent even when empty: 'no regions ticked' is a real state, and an
    // omitted parameter would mean 'no region filter' instead
    if (regs.length < 3) p.push("regions=" + regs.join(","));
    if (!show6) p.push("include_6mer=false");
    if (PAGE.gene) p.push("gene=" + encodeURIComponent(PAGE.gene));
    else if (PAGE.q) p.push("q=" + encodeURIComponent(PAGE.q));
    return u + (p.length ? "?" + p.join("&") : "");
  }

  function viewNote(){
    var bits = [], off = ["5UTR", "CDS", "3UTR"].filter(function(r){
      return !regOn[r]; });
    if (off.length)
      bits.push(off.map(function(r){ return RL[r]; }).join(" and ") + " hidden");
    if (!show6) bits.push("6mer sites hidden");
    if (PAGE.gene) bits.push(PAGE.gene + " only");
    else if (PAGE.q) bits.push("genes matching “" + PAGE.q + "”");
    var s = bits.length
      ? "This view: " + bits.join(", ") + ". Both files record which."
      : "No filters are active, so the two give the same file.";
    // the report ranks by the table's sort and ignores the row filters, so
    // say so rather than let the two controls look like one
    return s + " The report ranks by the table's current sort (" +
           PAGE.sort + ") and carries the top 20 terms per ontology.";
  }

  /* A report is rendered by the same worker that runs jobs, so it is asked
     for and then waited on. The finished report is offered as a link rather
     than opened automatically: a window.open() from a timer is not a user
     gesture, and every popup blocker would swallow it. */
  var REPPOLL = null;

  function expStat(html){ el("expstat").innerHTML = html || ""; }

  function buildReport(){
    if (REPPOLL || !JOBID) return;
    // 'all' is bounded by what the job actually found, and by the server's
    // own ceiling - a report is a document, not a dump
    var pick = parseInt(el("repn").value, 10);
    var n = pick || Math.min(PAGE.total || 50, 2000);
    expStat("building report…");
    // the ranking is the table's current sort, so the report and the screen
    // agree about what "top" means
    post("/jobs/" + JOBID + "/reports", {sort: PAGE.sort, top_n: n})
      .then(function(r){ watchReport(r.report_id); })
      .catch(function(e){ expStat(""); showErr(e); });
  }

  function watchReport(id){
    REPPOLL = setInterval(function(){
      api("/reports/" + id).then(function(r){
        if (r.status === "queued" || r.status === "running") return;
        clearInterval(REPPOLL); REPPOLL = null;
        if (r.status === "done")
          expStat('<a href="/reports/' + id + '.html" target="_blank" ' +
                  'rel="noopener">report ready — open ↓</a>');
        else
          expStat("report failed");
      }).catch(function(e){
        clearInterval(REPPOLL); REPPOLL = null;
        expStat(""); showErr(e);
      });
    }, 1500);
  }

  function loadPage(){
    api("/jobs/" + JOBID + "/genes?sort=" + PAGE.sort + "&limit=" + PAGE.limit +
        "&offset=" + PAGE.offset +
        (PAGE.gene ? "&gene=" + encodeURIComponent(PAGE.gene) : "") +
        (PAGE.q ? "&q=" + encodeURIComponent(PAGE.q) : ""))
      .then(function(p){
        PAGE.total = p.total_genes;
        applyData(p);
        el("results").hidden = false;
        el("runbox").hidden = true;
        render();
        pager();
        gsBoxes();
        netReload();
      }).catch(showErr);
  }

  function toolsChanged(){
    var n = document.querySelectorAll("#f_tools input:checked").length;
    var b = el("runbtn");
    b.disabled = !n;
    b.textContent = n ? ("Run " + n + " tool" + (n === 1 ? "" : "s")) : "Run";
    var hint = el("toolhint");
    if (hint) hint.textContent = n ? "" : "Select at least one analysis method.";
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
      ? (PAGE.gene + " only")
      : (!PAGE.total ? (PAGE.q ? "no gene matches “" + PAGE.q + "”" : "no genes")
         : (PAGE.q
            ? ("genes " + lo + "–" + hi + " of " + PAGE.total.toLocaleString() +
               " matching “" + PAGE.q + "”")
            : ("genes " + lo + "–" + hi + " of " +
               PAGE.total.toLocaleString())));
    // shown only while the table is filtered to one gene from a pathway term
    var back = el("ungene");
    back.hidden = !(PAGE.gene || PAGE.q);
    back.textContent = "← all genes";
    pageNumbers();
  }

  /* Numbered pages. With hundreds of genes a full run of numbers is
     unreadable, so the first, the last, and a window around the current one
     are shown, with gaps marked. */
  function pageNumbers(){
    var box = el("pgnums");
    if (!box) return;
    var per = PAGE.limit, n = Math.ceil(PAGE.total / per) || 0;
    var cur = Math.floor(PAGE.offset / per) + 1;
    if (n <= 1 || PAGE.gene){ box.innerHTML = ""; return; }

    var want = {1: 1, 2: 1};
    want[n] = 1; want[n - 1] = 1;
    for (var d = -2; d <= 2; d++) want[cur + d] = 1;
    var pages = Object.keys(want).map(Number)
      .filter(function(x){ return x >= 1 && x <= n; })
      .sort(function(a, b){ return a - b; });

    var html = '<button class="pgnum" data-p="' + (cur - 1) + '"' +
               (cur === 1 ? " disabled" : "") + ">‹</button>";
    var last = 0;
    pages.forEach(function(x){
      if (last && x > last + 1) html += '<span class="pggap">…</span>';
      html += '<button class="pgnum" data-p="' + x + '"' +
              (x === cur ? ' aria-current="true"' : "") + ">" + x + "</button>";
      last = x;
    });
    html += '<button class="pgnum" data-p="' + (cur + 1) + '"' +
            (cur === n ? " disabled" : "") + ">›</button>";
    box.innerHTML = html;
    box.querySelectorAll(".pgnum").forEach(function(b){
      b.addEventListener("click", function(){
        var target = +b.dataset.p;
        if (b.disabled || target < 1 || target > n) return;
        PAGE.offset = (target - 1) * per;
        loadPage();
      });
    });
  }

  function wire(){
    el("qform").addEventListener("submit", submit);
    document.addEventListener("change", function(e){
      if (e.target.closest && e.target.closest("#f_tools")) toolsChanged();
    });

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

    var ex = document.createElement("div");
    ex.className = "exp";
    ex.innerHTML =
      '<span class="expstat" id="expstat"></span>' +
      '<button class="linkbtn expbtn" id="expbtn" type="button" ' +
      'aria-haspopup="true" aria-expanded="false">Export ↓</button>' +
      '<div class="expmenu" id="expmenu" hidden>' +
      '<div class="exprow"><span>This view</span>' +
      '<button type="button" data-scope="view" data-fmt="tsv">TSV</button>' +
      '<button type="button" data-scope="view" data-fmt="xlsx">Excel</button>' +
      '</div>' +
      '<div class="exprow"><span>Whole job</span>' +
      '<button type="button" data-scope="all" data-fmt="tsv">TSV</button>' +
      '<button type="button" data-scope="all" data-fmt="xlsx">Excel</button>' +
      '</div>' +
      '<div class="expsep"><label class="expctl">Report genes ' +
      '<select id="repn">' +
      '<option value="25">top 25</option>' +
      '<option value="50" selected>top 50</option>' +
      '<option value="100">top 100</option>' +
      '<option value="0">all</option></select></label>' +
      '<button type="button" data-scope="report">Build report (HTML)</button>' +
      '</div>' +
      '<p class="expnote" id="expnote"></p></div>';
    // before the row count, not after it: appended last it wrapped onto a
    // second line of the flex toolbar and sat below everything else
    var rc = el("rowcount");
    if (rc && rc.parentNode === bar) bar.insertBefore(ex, rc);
    else bar.appendChild(ex);

    el("expbtn").addEventListener("click", function(e){
      e.stopPropagation();
      var m = el("expmenu");
      m.hidden = !m.hidden;
      el("expbtn").setAttribute("aria-expanded", String(!m.hidden));
      // written when the menu opens, so it always describes the table as it
      // is now rather than as it was when the page loaded
      if (!m.hidden) el("expnote").textContent = viewNote();
    });
    el("expmenu").addEventListener("click", function(e){
      var b = e.target.closest("button[data-scope]");
      if (!b || !JOBID) return;
      el("expmenu").hidden = true;
      el("expbtn").setAttribute("aria-expanded", "false");
      if (b.dataset.scope === "report") return buildReport();
      // Content-Disposition makes this a download, not a navigation
      window.location = exportURL(b.dataset.scope, b.dataset.fmt);
    });
    document.addEventListener("click", function(e){
      var m = el("expmenu");
      if (m && !m.hidden && !(e.target.closest && e.target.closest(".exp"))){
        m.hidden = true;
        el("expbtn").setAttribute("aria-expanded", "false");
      }
    });

    function enrExport(ext){
      if (!ENR || !ENR.run) return;
      var p = [];
      // the open tab and the search box are what the reader is looking at
      if (ENRSRC) p.push("source=" + encodeURIComponent(ENRSRC));
      if (ENRQ) p.push("q=" + encodeURIComponent(ENRQ));
      window.location = "/enrichment/" + ENR.run.run_id + "/terms." + ext +
                        (p.length ? "?" + p.join("&") : "");
    }
    el("enrexp").addEventListener("click", function(){ enrExport("tsv"); });
    el("enrexpx").addEventListener("click", function(){ enrExport("xlsx"); });

    var d = document.createElement("div");
    d.className = "pager";
    d.innerHTML = '<button class="linkbtn" id="ungene" type="button" hidden></button>' +
                  '<span id="pagelbl"></span><span id="pgnums"></span>';
    bar.appendChild(d);
    el("ungene").addEventListener("click", function(){
      PAGE.gene = null; PAGE.q = ""; el("geneq").value = "";
      el("geneqx").hidden = true; PAGE.offset = 0; loadPage();
    });

    var sb = document.createElement("div");
    sb.className = "tsearch gsearch";
    sb.innerHTML = '<label for="geneq">Search genes</label>' +
      '<div class="tsbox"><input type="search" id="geneq" autocomplete="off" ' +
      'placeholder="gene symbol or Entrez id — searches every result, not this page">' +
      '<button type="button" id="geneqx" hidden aria-label="clear">×</button></div>';
    bar.parentNode.insertBefore(sb, bar);
    el("geneq").addEventListener("input", function(){
      clearTimeout(GTIMER);
      GTIMER = setTimeout(function(){
        PAGE.q = el("geneq").value.trim();
        PAGE.gene = null;
        PAGE.offset = 0;
        el("geneqx").hidden = !PAGE.q;
        loadPage();
      }, 200);
    });
    el("geneqx").addEventListener("click", function(){
      el("geneq").value = ""; PAGE.q = ""; el("geneqx").hidden = true;
      PAGE.offset = 0; loadPage(); el("geneq").focus();
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
  var NETSEEN = {};
  var ENR = null, ENRSRC = null, ENRLIMIT = 20, ENRPOLL = null;
  var ENRQ = "", QTIMER = null;
  // p ascending is the scientific default: strongest term first. Sorting by
  // gene count answers a different question - which term the list touches most
  // - so it is offered but never the default; a big term is not a strong one.
  var ENRSORT = "p", ENRDESC = false;

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
      run.n_background.toLocaleString() + " genes.";

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
    // Versions and the KEGG fetch time are off the page by request. They are
    // still on the run row and in the TSV export, so the result stays
    // reproducible even though the panel no longer prints them.
    el("enrichmeta").textContent = "";

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
    var rows = (ENR.terms || []).slice();
    rows.sort(function(a, b){
      var d = ENRSORT === "genes"
        ? a.k_in_term_and_list - b.k_in_term_and_list
        : (a.p_adjust - b.p_adjust) || (a.p_value - b.p_value);
      return ENRDESC ? -d : d;
    });
    document.querySelectorAll(".terms th.sortable").forEach(function(th){
      var on = th.dataset.sort === ENRSORT;
      if (on) th.setAttribute("aria-sort", ENRDESC ? "descending" : "ascending");
      else th.removeAttribute("aria-sort");
      th.querySelector(".arrow").textContent = on ? (ENRDESC ? "\u25bc" : "\u25b2") : "\u2195";
      if (!th.dataset.wired){
        th.dataset.wired = "1";
        th.addEventListener("click", function(){
          if (ENRSORT === th.dataset.sort) ENRDESC = !ENRDESC;
          else { ENRSORT = th.dataset.sort; ENRDESC = (ENRSORT === "genes"); }
          renderEnrich();
        });
      }
    });
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
         ? ("Showing " + total + " of " + inSrc + " terms matching \u201c" +
            ENRQ + "\u201d")
         : ("Showing " + shown + " of " + inSrc + " terms"));
    // exportable as soon as there are terms; the search box and the open tab
    // narrow the file the same way they narrow the panel
    el("enrexp").hidden = el("enrexpx").hidden = !(run.status === "done" && inSrc);
    // the shared-term layer only exists once an enrichment has finished, so
    // the network is redrawn once per completed run rather than every render
    if (run.status === "done" && !NETSEEN[run.run_id]){
      NETSEEN[run.run_id] = 1;
      netReload();
    }
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
      (t.q_value == null ? ""
        : stat("q-value", "<code>" + t.q_value.toExponential(2) + "</code>")) +
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
    netWire();
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
      el("sources").textContent = "";
      tools.forEach(function(t){ TOOLMETA[t.name] = t; });

      // Nothing is ticked. These are analysis methods the user chooses, and
      // a pre-ticked box is a decision made on their behalf that they may
      // never notice they did not make.
      var TOOLTITLE = {seed: "Seed Analysis", rnahybrid: "RNAhybrid",
                       targetscan: "TargetScan", mirtarbase: "miRTarBase"};
      el("f_tools").innerHTML = '<span>Tools</span><div class="toolpick">' +
        tools.map(function(t){
          return '<label class="tp"><input type="checkbox" value="' + t.name +
            '"><span class="tpn">' + (TOOLTITLE[t.name] || t.name) + "</span>" +
            '<span class="tps">' + (t.question || "") + "</span>" +
            "</label>";
        }).join("") + "</div>";
      toolsChanged();

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

NETWORK_JS = """
  /* ---------- target network ----------
     A second reading of rows already on the page, so it must agree with the
     table: the server ranks genes with the same function the table uses, and
     this code only draws what it is handed. */
  var NET = null, NETDATA = null;

  function nesc(s){
    return String(s == null ? "" : s).replace(/&/g, "&amp;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function netPalette(){
    // read the page's own variables rather than inventing a second palette
    var c = getComputedStyle(document.documentElement);
    function v(n, d){ var x = c.getPropertyValue(n).trim(); return x || d; }
    return {accent: v("--accent", "#1f4e79"), ink: v("--ink", "#15181d"),
            line: v("--line", "#e3e6ea"), muted: v("--muted", "#666f7a"),
            surface: v("--surface", "#ffffff"),
            val: "#1a6b3c", valbg: "#e2f1e8", predbg: "#eaeff4"};
  }

  function netStyleNode(n, P){
    if (n.group === "mirna")
      return {shape: "diamond", size: 26, color: {background: P.accent,
              border: P.accent, highlight: {background: P.accent,
              border: P.ink}},
              font: {color: P.ink, size: 16, face: "Inter, system-ui",
                     vadjust: -4}};
    // Validated is not a better prediction, it is a different kind of claim,
    // so it gets its own colour rather than a place on one scale.
    var on = n.group === "validated";
    return {shape: "dot",
            color: {background: on ? P.valbg : P.predbg,
                    border: on ? P.val : P.accent,
                    highlight: {background: on ? P.val : P.accent,
                                border: P.ink}},
            font: {color: P.ink, size: 13, face: "Inter, system-ui"}};
  }

  function netHint(){
    return "<h4>Click a node or a link</h4>Nodes are genes; the diamond is " +
           "the miRNA. A solid link means a tool reported that target, and " +
           "a dotted link means two genes appear together in enriched terms.";
  }

  function drawNetwork(d){
    NETDATA = d;
    var P = netPalette();
    el("k1").style.background = P.accent;
    el("k2").style.background = P.val;
    el("k3").style.background = P.accent;
    el("k3").style.opacity = "0.35";

    var nodes = d.nodes.map(function(n){
      var s = netStyleNode(n, P);
      s.id = n.id; s.label = n.label; s.value = n.value;
      s.title = n.group === "mirna"
        ? n.label + " · " + n.accession + " · " + n.n_targets + " targets"
        : n.label + " · " + n.n_tools + " of 4 tools" +
          (n.strong_functional ? " · " + n.strong_functional +
           " strong functional experiments" : "");
      return s;
    });

    var edges = d.edges.map(function(e, i){
      var shared = e.kind === "shared_terms";
      return {id: "e" + i, from: e.from, to: e.to, value: e.value,
              title: e.title,
              dashes: shared ? [2, 4] : false,
              width: shared ? 1 : undefined,
              color: {color: shared ? P.line : P.muted,
                      highlight: P.accent, opacity: shared ? 0.85 : 1},
              smooth: shared ? {type: "continuous"} : false};
    });

    var opts = {
      nodes: {scaling: {min: 10, max: 32}, borderWidth: 1.5},
      edges: {scaling: {min: 1, max: 6}},
      // improvedLayout is quadratic and stalls past a few hundred nodes;
      // the physics settle is enough and starts drawing immediately
      layout: {improvedLayout: false},
      physics: {barnesHut: {gravitationalConstant: -9000, springLength: 135,
                            springConstant: 0.03, avoidOverlap: 0.12},
                stabilization: {iterations: 220}},
      interaction: {hover: true, tooltipDelay: 120, keyboard: false,
                    navigationButtons: false}
    };

    if (NET) NET.destroy();
    NET = new vis.Network(el("netcanvas"),
                          {nodes: new vis.DataSet(nodes),
                           edges: new vis.DataSet(edges)}, opts);
    NET.on("click", function(pr){
      if (pr.nodes.length) return netShowNode(pr.nodes[0]);
      if (pr.edges.length) return netShowEdge(pr.edges[0]);
      el("netinfo").innerHTML = netHint();
    });
    NET.once("stabilizationIterationsDone", function(){
      if (!el("netphys").checked) NET.setOptions({physics: {enabled: false}});
    });

    var m = d.meta;
    el("netstate").textContent = m.genes_shown + " genes · " +
      m.n_target_edges + " target links" +
      (m.n_shared_edges ? " · " + m.n_shared_edges + " shared-term links" : "");
    el("nethead").innerHTML =
      "<b>" + nesc(d.mirna.name) + "</b> and its " + m.genes_shown +
      (m.truncated ? " highest-ranked targets of " + m.genes_total : " targets") +
      ", ranked by " + nesc(m.sort) + ".";
    el("netinfo").innerHTML = netHint();

    // Say what the picture is missing rather than let an empty-looking graph
    // imply there was nothing to find.
    var note = [];
    if (!m.shared_layer)
      note.push("No pathway analysis has been run on this job, so genes are " +
                "not linked to each other yet — run one above and the " +
                "shared-term links appear.");
    else {
      note.push(m.genes_in_shared_layer + " of these genes carry shared-term " +
                "links. A gene with none was either not in the gene set the " +
                "enrichment tested, or shares no enriched term with another " +
                "gene shown here.");
      var s = m.shared_stats || {};
      if (s.terms_too_broad)
        note.push(s.terms_too_broad + " term" +
          (s.terms_too_broad === 1 ? " was" : "s were") + " skipped for " +
          "containing more than " + s.term_size_cap + " of these genes: a " +
          "term holding most of the list links everything to everything and " +
          "says nothing about which genes belong together.");
      if (s.edges_dropped)
        note.push(s.edges_dropped + " weaker pairings were dropped to keep " +
                  "the graph readable; raise the shared-terms threshold to " +
                  "see the strongest ones alone.");
    }
    el("netnote").innerHTML = note.join(" ");
    el("netbox").hidden = false;
  }

  function netRow(k, v){
    return v == null || v === "" ? "" :
      "<dt>" + nesc(k) + "</dt><dd>" + v + "</dd>";
  }

  function netShowNode(id){
    var n = null;
    (NETDATA.nodes || []).forEach(function(x){ if (x.id === id) n = x; });
    if (!n) return;
    if (n.group === "mirna"){
      el("netinfo").innerHTML = "<h4>" + nesc(n.label) + "</h4><dl>" +
        netRow("accession", nesc(n.accession)) +
        netRow("targets shown", n.n_targets) + "</dl>";
      return;
    }
    var RL = {"5UTR": "5\\u2032UTR", "CDS": "CDS", "3UTR": "3\\u2032UTR"};
    el("netinfo").innerHTML =
      "<h4>" + nesc(n.label) + " <span class='txid'>" + nesc(n.refseq) +
      "</span></h4><dl>" +
      netRow("tools reporting", n.tools.map(nesc).join(", ")) +
      netRow("regions", (n.regions || []).map(function(r){
        return RL[r] || r; }).join(" · ")) +
      netRow("best seed site", n.seed_site ? nesc(n.seed_site) +
             (n.n_seed > 1 ? " (" + n.n_seed + " sites)" : "") : null) +
      netRow("RNAhybrid \\u0394G", n.dg == null ? null : n.dg.toFixed(1) +
             " kcal/mol" + (n.n_rh > 1 ? " (best of " + n.n_rh + ")" : "")) +
      netRow("TargetScan context++", n.context == null ? null :
             n.context.toFixed(3)) +
      netRow("TargetScan PCT", n.pct == null ? null : n.pct) +
      netRow("miRTarBase", n.strong_functional ? n.strong_functional +
             " strong functional experiments" : null) +
      "</dl><button class='linkbtn' id='netgene' type='button'>" +
      "show this gene's binding sites \\u2192</button>";
    var b = el("netgene");
    if (b) b.addEventListener("click", function(){
      // the same jump the pathway panel makes: from a picture back to the rows
      PAGE.gene = n.label; PAGE.offset = 0;
      el("ungene").hidden = false;
      el("ungene").textContent = "\\u2190 all genes";
      loadPage();
      el("results").scrollIntoView({behavior: "smooth", block: "start"});
    });
  }

  function netShowEdge(id){
    var i = parseInt(String(id).slice(1), 10);
    var e = (NETDATA.edges || [])[i];
    if (!e) return;
    if (e.kind === "target"){
      el("netinfo").innerHTML = "<h4>" + nesc(e.to) + "</h4><dl>" +
        netRow("reported by", e.tools.map(nesc).join(", ")) +
        netRow("tools agreeing", e.value + " of 4") + "</dl>" +
        "<p class='netnote'>Agreement is the only cross-tool number here. " +
        "Their scores are on different scales and are never combined.</p>";
      return;
    }
    el("netinfo").innerHTML = "<h4>" + nesc(e.from) + " \\u2014 " +
      nesc(e.to) + "</h4><dl>" + netRow("shared enriched terms", e.shared) +
      netRow("including", e.terms.map(nesc).join("<br>")) + "</dl>";
  }

  function netReload(){
    if (!JOBID || typeof vis === "undefined") return;
    api("/jobs/" + JOBID + "/network?sort=" + PAGE.sort +
        "&top_n=" + el("netn").value +
        "&min_shared=" + el("netmin").value)
      .then(drawNetwork)
      .catch(function(e){
        el("netbox").hidden = false;
        el("netstate").textContent = "unavailable";
        el("netinfo").textContent = (e && e.message) || "could not load";
      });
  }

  function netWire(){
    if (typeof vis === "undefined"){
      // vendored locally, so this only happens if web/vendor is missing
      el("netnote").textContent = "The network library did not load: " +
        "web/vendor/vis-network.min.js is missing.";
      return;
    }
    el("netn").addEventListener("change", netReload);
    el("netmin").addEventListener("change", netReload);
    el("netfit").addEventListener("click", function(){
      if (NET) NET.fit({animation: true});
    });
    el("netphys").addEventListener("change", function(e){
      if (NET) NET.setOptions({physics: {enabled: e.target.checked}});
    });
    el("netinfo").innerHTML = netHint();
  }
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HEAD + keep + """  </div>

  <p class="sources" id="sources"></p>

</div>

<script src="vendor/vis-network.min.js"></script>
<script>
""" + script + NETWORK_JS + TAIL_JS + """</script>
</body>
</html>
""")
print("wrote", OUT, OUT.stat().st_size, "bytes")
