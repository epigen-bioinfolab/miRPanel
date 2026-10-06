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
                  '<h2>Tools Run<em id="runid"></em></h2>')]:
    assert keep.count(old) == 1, old
    keep = keep.replace(old, new)

# Section headings are Title Case throughout, so the two that come straight
# from the approved layout are brought into line here rather than by editing
# the layout, which stays the record of what was approved.
for _a, _b in [("<h2>Binding map", "<h2>Binding Map"),
               ("<h3>How to read this page</h3>",
                "<h3>How To Read This Page</h3>")]:
    assert keep.count(_a) == 1, _a[:40]
    keep = keep.replace(_a, _b)

# the pathway-analysis panel goes between the table and the notes
_notes = keep.index('<div class="notes">')
keep = keep[:_notes] + """<section class="panel" id="agree" hidden>
    <h2>Tool Agreement<em id="agstate"></em></h2>
    <div class="panel-body">
      <div class="fgroup" id="agtools"><span>Tools</span></div>
      <div id="agfig"></div>
      <p class="say agcap" id="agcap"></p>
      <div id="agdetail" hidden></div>
    </div>
  </section>

  <section class="panel" id="enrich">
    <h2>Pathway Analysis<em id="gscount">nothing selected</em></h2>
    <div class="panel-body">
      <p class="say gsextnote" id="gsextnote" hidden>Showing enrichment for the genes picked in Tool Agreement — the filters below were not used for this run.</p>
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
    <h2>Enriched Terms<em id="enrichstate"></em></h2>
    <div class="panel-body">
      <p id="enrichhead"></p>
      <p id="enrichmeta"></p>
      <div class="tabs" id="enrichtabs"></div>
      <div class="tsearch">
        <label for="termq">Search pathways, terms and genes</label>
        <div class="tsbox">
          <input type="search" id="termq" autocomplete="off"
                 placeholder="term, ID or gene — mesenchyme, GO:0060485, PTEN">
          <button type="button" id="termqx" hidden aria-label="clear">×</button>
        </div>
      </div>
      <table class="terms"><thead><tr>
        <th></th><th>Term</th>
        <th class="sortable" data-sort="genes">Genes<span class="arrow"></span></th>
        <th>Gene symbols</th>
        <th class="sortable" data-sort="p">Adjusted p<span class="arrow"></span></th>
      </tr></thead><tbody id="termbody"></tbody></table>
      <div class="termfoot">
        <span id="termcount"></span>
        <button class="linkbtn" id="termmore" type="button" hidden></button>
        <button class="linkbtn expright" id="enrexpx" type="button" hidden>Export terms (Excel) ↓</button>
        <button class="linkbtn" id="enrexp" type="button" hidden>TSV ↓</button>
      </div>
    </div>
  </section>

  <section class="panel" id="netbox" hidden>
    <h2>Target Network<em id="netstate"></em></h2>
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
_b0 = keep.index('<section class="panel browser" id="mapsection">')
_b1 = keep.index("</section>", _b0) + len("</section>")
_map = keep[_b0:_b1]
keep = keep[:_b0] + keep[_b1:]
_tbl = keep.index('<div class="toolbar">')
keep = (keep[:_tbl] + _map +
        '\n\n  <h2 class="sectitle" id="resulttable">The Result Table</h2>\n  ' + keep[_tbl:])

# The tool key is reference material, not a step in the workflow, so it moves
# down beside the notes that explain how to read the page.
_t0 = keep.index('<section class="toolkey">')
_t1 = keep.index("</section>", _t0) + len("</section>")
_tk = keep[_t0:_t1]
keep = keep[:_t0] + keep[_t1:]
_n = keep.index('<div class="notes">')
keep = (keep[:_n] + '<div id="guidesHome"></div>\n\n  ' + _tk +
        "\n\n  " + keep[_n:])

# miRanda was dropped from the project, so its column comes out rather than
# standing there permanently reading "not built". An empty column for a tool
# that will never exist is worse than no column.
for _a, _b in [
    ('<th colspan="1" class="gsep">Not yet built</th>',
     '<th colspan="2" class="gsep">scanMiR</th>'),
    ('<th colspan="1" class="gsep">RNAhybrid</th>',
     '<th colspan="2" class="gsep">RNAhybrid</th>'),
    ('<th class="colsep"><div class="hcell"><span class="hn">ML model \u00b7 miRanda'
     '</span><span class="hu">later phases</span></div></th>',
     '<th class="colsep"><div class="hcell"><span class="hn">Best site</span>'
     '<span class="hu">type \u00b7 position</span></div></th>'
     '<th><div class="hcell"><span class="hn">log Kd</span>'
     '<span class="hu">affinity \u2193</span></div></th>'),
    ('<th class="colsep"><div class="hcell"><span class="hn">\u0394G</span>'
     '<span class="hu">kcal/mol \u00b7 bar 0 to \u221235</span></div></th>',
     '<th class="colsep"><div class="hcell"><span class="hn">Best duplex</span>'
     '<span class="hu">position \u00b7 region</span></div></th>'
     '<th><div class="hcell"><span class="hn">\u0394G</span>'
     '<span class="hu">kcal/mol</span></div></th>'),
    ('<span class="hu">bar 0 to \u22121</span>',
     '<span class="hu">site context score</span>'),
    ('<th colspan="2" class="gsep">Seed analyser \u2014 ours</th>',
     '<th colspan="2" class="gsep">Seed analyser</th>'),
    ]:
    assert keep.count(_a) == 1, _a[:50]
    keep = keep.replace(_a, _b)

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
  var TX = {}, SEED = [], RH = [], TS = {}, MT = {}, SMS = [];

""" + script[script.index(b):]

a = '  document.getElementById("prov").textContent ='
b = "  /* ---------- tool guide slides ---------- */"
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
    // RNAhybrid in two cells: where the duplex is, then how tight it is.
    // It reports no site type - a fold is not a seed match - so the first
    // cell carries position and region only.
    var rhEmpty = ran("rnahybrid") ? none() : nrun();
    cells.push('<td class="colsep">' + (r
      ? '<span class="seq">' + r[2].toLocaleString() + "\u2013" +
        r[3].toLocaleString() + "</span>" +
        (r[1] ? '<span class="sub2">' + RL[r[1]] + "</span>" : "")
      : rhEmpty) + "</td>");
    cells.push('<td class="num">' + (r
      ? r[4].toFixed(1) + meter(Math.abs(r[4]) / 35) +
        (nRh > 1 ? '<span class="say">best&nbsp;of&nbsp;' + nRh +
                   " foldings</span>" : "")
      : rhEmpty) + "</td>");

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
    // scanMiR, in two cells like TargetScan: what and where, then how
    // tightly. An empty cell means one of three different things and they
    // must not look alike - the tool was not run, it ran and found nothing,
    // or it has no model for this miRNA (scanMiRData is built on miRBase 22
    // and 243 human miRNAs had their seed revised in Release 23).
    var sm = bestSm(g), nSm = smOf(g).length;
    var smRun = ((JOBST && JOBST.tools) || []).filter(
      function(t){ return t.tool === "scanmir"; })[0];
    var smNoModel = !!(smRun && smRun.message &&
      /no usable model|seed was revised|no scanMiR KdModel/i.test(smRun.message));
    var smEmpty = !ran("scanmir") ? nrun() : (smNoModel ? ncov() : none());
    cells.push('<td class="colsep">' + (sm
      ? '<span class="site' + (SITE_CLASS[sm[2]] ? " " + SITE_CLASS[sm[2]] : "") +
        '">' + sm[2] + "</span>" +
        '<span class="sub2">' + sm[3].toLocaleString() + "\u2013" +
        sm[4].toLocaleString() + (sm[1] ? " \u00b7 " + RL[sm[1]] : "") + "</span>"
      : smEmpty) + "</td>");
    cells.push('<td class="num">' + (sm
      ? sm[5].toFixed(3) + meter(Math.min(1, Math.abs(sm[5]) / 5)) +
        (nSm > 1 ? '<span class="say">best&nbsp;of&nbsp;' + nSm +
                   " sites</span>" : "")
      : smEmpty) + "</td>");
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
  /* the button gets a little air below the sentence rather than sitting
     pinned to its baseline - a small, deliberate nudge, not a new layout */
  #gsrun{margin-top:9px}
  #gscount{font-family:'JetBrains Mono','SFMono-Regular',Menlo,monospace;text-transform:none;letter-spacing:0}
  #gscount.ok{color:var(--ok)}
  #gscount.warn{color:var(--warn)}

  /* ---- when this panel's own gene run came from a Tool Agreement region
     click, its tick-boxes were never read - so they must not look like the
     source of what is showing below. Faded until the user actually touches
     a filter or presses "Run GO and KEGG" themselves, at which point the
     panel and its results agree again. The button stays fully active in
     both states: it always has a real job, either confirming the filter
     picture or replacing the region-driven run with one. ---- */
  /* .say's base rule (layout-source.html) caps inline annotations at
     21ch, which is right for a table-cell tag but wraps a full sentence
     into a stack of short lines - override it here so this note reads
     as one line the way .gsfoot .say already does for its own case. */
  .gsextnote{margin:0 0 12px;font-size:12.5px;line-height:1.5;color:var(--warn);
    max-width:none;white-space:nowrap;overflow-x:auto}
  #enrich.gs-external .gsgrid,
  #enrich.gs-external .gsbar,
  #enrich.gs-external #gscount,
  #enrich.gs-external #gssentence{opacity:.42;filter:grayscale(35%);
    transition:opacity .25s,filter .25s}
  #enrich.gs-external #gsrun{transition:opacity .25s}
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

  /* The table filtered down to one gene is easy to land on mid-scroll (a
     click from the agreement diagram, a pathway term, the network view)
     and mistake for the whole table, or for whatever else is on screen -
     see focusGene(). Deliberately louder than #pagelbl's small "X only"
     text, and placed directly above the table by wire() so it is the
     first thing in view when the page scrolls there. */
  .genebanner{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
    margin:4px 0 12px;padding:9px 14px;background:var(--accent-wash);
    border:1px solid var(--accent);border-radius:6px;
    font-size:15.5px;color:var(--ink)}
  .genebanner b{font-family:'IBM Plex Mono',monospace;color:var(--accent);
    font-weight:700}
  .genebanner .linkbtn{font-size:12.5px;color:var(--accent);
    border-bottom-color:var(--accent)}
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
  /* Excel is the format that actually looks like a table when opened -
     styled, frozen header, no 30-empty-column sparseness from a job that
     ran five tools. Filled instead of outlined so it reads as the answer
     to "give me something well organised", with TSV still one click away
     for R/pandas. */
  .exprow>button.expprimary{background:var(--accent);color:var(--accent-ink);
    border-color:var(--accent)}
  .exprow>button.expprimary:hover{filter:brightness(1.08)}
  .exphint{margin:2px 10px 6px;font-size:11.5px;line-height:1.45;
    color:var(--faint)}

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
  #enrexp{margin-left:7px}
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
  .netkey i.dash{border-top-style:dashed;border-top-color:var(--accent)}
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

# Last in the cascade on purpose: one place to adjust typography, spacing and
# section prominence without unpicking the rules the approved layout set.
POLISH_CSS = """
  /* ---- the masthead: a fixed dark-blue banner, independent of the site's
     own light/dark theme, carrying the product name and a row of links to
     every section on the page. Approved design, 23 Sep - see agreement_design
     for the reference mock. Colours are hardcoded rather than themed: the
     banner is a fixed brand element, not a themed surface. ---- */
  .masthead{
    margin:0 0 48px;padding:0;border-bottom:0;gap:0;
    position:relative;overflow:hidden;border-radius:10px;
    background:linear-gradient(115deg,#123a78 0%,#0c3268 55%,#0a2c5c 100%);
  }
  .masthead, .masthead *{font-family:Arial,Helvetica,sans-serif!important}
  .mh-inner{max-width:760px;margin:0 auto;padding:38px 40px 0;text-align:center}
  /* Three columns so the middle one - the name plus its maker line, which
     must center on each other and nothing wider - lands in the true center
     of the banner regardless of the pill's width. The pill sits in its own
     column, right next to the name, balanced by an equal empty column on
     the left rather than being folded into the centered group. */
  .brand-row{display:grid;grid-template-columns:1fr auto 1fr;
    align-items:start;column-gap:14px}
  .brand-name-col{grid-column:2;display:flex;flex-direction:column;
    align-items:center}
  #title{font-size:clamp(34px,5vw,52px);font-weight:800;letter-spacing:-.02em;
    color:#fff;margin:0;line-height:1}
  .kicker{grid-column:3;justify-self:start;margin-top:11px;
    display:inline-block;font-size:13px;font-weight:700;color:#fff;
    text-transform:none;letter-spacing:0;
    border:1.5px solid rgba(255,255,255,.55);background:rgba(255,255,255,.10);
    border-radius:999px;padding:6px 16px;white-space:nowrap}
  .maker{font-size:16px;color:rgba(255,255,255,.94);margin:7px 0 0;
    font-weight:600;letter-spacing:.01em}
  .masthead .sub2line{font-size:clamp(18px,2.1vw,21px);font-weight:700;
    color:#fff;letter-spacing:-.012em;line-height:1.35;max-width:none;
    margin:20px 0 0}
  /* #tagline carries an ID rule from the page's older, plain-masthead CSS
     (color:var(--muted)) - an ID beats any number of classes, so this has
     to match or beat that specificity rather than just come later. */
  .masthead #tagline{font-size:15.5px;line-height:1.65;color:#fff;
    font-weight:500;max-width:720px;margin:12px auto 0}

  /* ---- section nav: one row of links to every part of the page. Before a
     search only New Search / Query / the two reference decks make sense to
     visit, so the rest start disabled (native <button disabled>, not just
     dimmed - a click on a section that doesn't exist yet should do nothing).
     positionGuides() flips the gate the moment #results shows or hides. ---- */
  .navrow{margin:26px 0 0;border-top:1px solid rgba(255,255,255,.18);
    display:flex;justify-content:center;flex-wrap:wrap;padding:0 6px}
  .navitem{display:flex;align-items:center;gap:7px;padding:14px 16px;
    font-size:13px;font-weight:600;color:#fff;white-space:nowrap;
    cursor:pointer;position:relative;background:none;border:0;
    font-family:inherit;transition:opacity .2s;appearance:none}
  .navitem svg{width:15px;height:15px;flex:none;opacity:.92}
  .navitem:disabled{opacity:.38;cursor:default}
  .navitem:not(:disabled):hover{opacity:.82}

  /* ---- sections announce themselves ----
     The panel heading was a 10px uppercase mono label, which read as a
     caption rather than a section. Each one is now a real heading with a
     heavy rule under it in the accent colour. */
  .panel>h2, .sectitle, .notes h3{
    font-family:'Inter',system-ui,sans-serif;
    font-size:19px;font-weight:700;letter-spacing:-.01em;
    text-transform:none;color:var(--ink)}
  .panel>h2{
    padding:15px 18px 12px;background:var(--surface);
    border-bottom:3px solid var(--accent);
    align-items:baseline}
  .panel>h2 em{
    font-size:13.5px;font-weight:500;color:var(--muted);
    letter-spacing:0;text-transform:none;white-space:nowrap}
  .sectitle{
    margin:0 0 18px;padding-bottom:12px;
    border-bottom:3px solid var(--accent)}
  .notes h3{margin:0 0 14px;padding-bottom:12px;
    border-bottom:3px solid var(--accent)}

  /* ---- room to breathe between sections ---- */
  section.panel{margin:0 0 40px}
  .context{margin-bottom:40px;gap:26px 40px}
  .tablewrap{margin-bottom:40px}
  h2.sectitle{margin-top:48px}
  .toolbar{margin-bottom:18px}
  .notes{margin-top:48px}
  .panel-body{padding:18px}

  /* ---- the result table: every cell centred under its heading ---- */
  table.results{font-size:13.5px}
  table.results thead th,
  table.results thead tr.grouprow th{text-align:center;vertical-align:bottom}
  table.results tbody td,
  table.results tbody td.num{text-align:center;vertical-align:middle;
    padding-top:11px;padding-bottom:11px}
  table.results tbody td .sub2,
  table.results tbody td .txid{text-align:center}
  table.results tbody td .gene{font-size:14.5px}

  /* The enrichment table keeps its term names left-aligned: a long sentence
     centred is harder to scan, not easier. Its numbers centre like the rest. */
  .terms{font-size:13.5px}
  .terms td, .terms th{vertical-align:middle;padding-top:10px;
    padding-bottom:10px}
  .terms td:nth-child(n+3), .terms th:nth-child(n+3){text-align:center}

  /* ---- nothing readable is left at caption size ---- */
  .txid, .hu, .gsnote, .say, .sub2, #rowcount, .termfoot,
  .expnote, .netnote, .netkey, .expstat, .sources{font-size:13.5px}
  .txid, .sub2{line-height:1.5}
  .empty{font-size:13.5px}
  .notes li{font-size:14px;line-height:1.65;margin-bottom:9px}
  .netinfo{font-size:13.5px}
  .netinfo dt{font-size:13px}
  .netinfo dd{font-size:13.5px}
  .ctl, .switch{font-size:13.5px}
  .mapbody, .maphint{font-size:13.5px}
"""

# ---- scanMiR in the per-site detail table ----------------------------------
# The expanded row lists every stored site for a gene. scanMiR measures
# position, so it belongs there beside the seed analyser and RNAhybrid - and
# seeing the three side by side is the point: they agree on PDCD4's 8mer and
# disagree about which PTEN site is strongest.
a = "  function overlaps(s,r){"
assert script.count(a) == 1
script = script.replace(a, """  function smOf(g){
    return SMS.filter(function(m){
      // a site with no region of its own is never hidden by a region box
      return m[0] === g && (m[1] == null || regOn[m[1]]);
    });
  }
  function bestSm(g){
    var a = smOf(g);
    // lowest log Kd wins - the tool's own direction, the same rule
    // ranking.py applies server-side, so the column and the sort agree
    return a.length ? a.slice().sort(function(x, y){ return x[5] - y[5]; })[0]
                    : null;
  }

""" + a, 1)

# one more column in the detail table, so the expanded row must span one more
a = '<td colspan="9">'
assert script.count(a) == 1
script = script.replace(a, '<td colspan="11">', 1)

a, b = "  function rawSites(g){", "  function order(){"
assert script.count(a) == 1 and script.count(b) == 1
script = script[:script.index(a)] + r"""  function rawSites(g){
    var rows = [];
    seedOf(g).forEach(function(s){
      var ov = rhOf(g).filter(function(r){return overlaps(s,r);})[0];
      rows.push({tool:"seed", region:s[1], site:s[2], a:s[3], b:s[4],
                 dg:null, kd:null, k:"seed|"+s[3],
                 note: ov ? "inside RNAhybrid duplex "+ov[2]+"–"+ov[3] : ""});
    });
    rhOf(g).forEach(function(r){
      var ov = seedOf(g).filter(function(s){return overlaps(s,r);})[0];
      rows.push({tool:"rnahybrid", region:r[1], site:null, a:r[2], b:r[3],
                 dg:r[4], kd:null, k:"rh|"+r[2],
                 note: ov ? "contains "+ov[2]+" seed site "+ov[3]+"–"+ov[4] : ""});
    });
    smOf(g).forEach(function(m){
      // scanMiR reports every site as an 8 nt window whatever its type, so a
      // 6mer's coordinates sit one nucleotide before the seed analyser's.
      // The agreement note therefore tests for overlap, never equality.
      var ov = seedOf(g).filter(function(s){
        return s[3] <= m[4] && s[4] >= m[3]; })[0];
      rows.push({tool:"scanmir", region:m[1], site:m[2], a:m[3], b:m[4],
                 dg:null, kd:m[5], k:"sm|"+m[3],
                 note: ov ? "overlaps "+ov[2]+" seed site "+ov[3]+"–"+ov[4] : ""});
    });
    rows.sort(function(a,b){return a.a-b.a;});

    var body = rows.map(function(x){
      return '<tr class="clickable'+(selSite===x.k?" sitesel":"")+'" data-k="'+x.k+'">'+
        "<td>"+toolLabel(x.tool)+"</td>"+
        "<td>"+(x.region?'<span class="region '+RC[x.region]+'">'+RL[x.region]+
                         "</span>":none())+"</td>"+
        "<td>"+(x.site?'<span class="site'+(SITE_CLASS[x.site]?" "+SITE_CLASS[x.site]:"")+
                       '">'+x.site+"</span>":none())+"</td>"+
        '<td class="num">'+x.a.toLocaleString()+"–"+x.b.toLocaleString()+"</td>"+
        '<td class="num">'+(x.dg===null?none():x.dg.toFixed(1))+"</td>"+
        '<td class="num">'+(x.kd===null?none():x.kd.toFixed(3))+"</td>"+
        '<td class="agree">'+(x.note?"↔ "+x.note:"")+"</td></tr>";
    }).join("");

    var nAgree = rows.filter(function(x){return x.note;}).length;
    if (!rows.length)
      return '<div class="dethead">No tool that measures position found a site in '+g+
             " with the current filters.</div>";

    return '<div class="dethead">'+rows.length+" record"+(rows.length===1?"":"s")+" for "+g+
      ", one row each, exactly as stored — from the three tools that measure position."+
      (nAgree?" The Agreement column marks where two tools point at overlapping nucleotides.":"")+
      " TargetScan and miRTarBase report one value for the whole gene, so they have no row here.</div>"+
      '<table class="sites"><thead><tr><th>Tool</th><th>Region</th><th>Site</th>'+
      "<th>Position</th><th>ΔG</th><th>log Kd</th><th>Agreement</th></tr></thead><tbody>"+
      body+"</tbody></table>";
  }

""" + script[script.index(b):]


# ---- the binding map gets a lane per tool, and a flash target -------------
# Three tools measure position, so the map shows three lanes, each named.
# Without the names a reader cannot tell which row is whose, and the whole
# point of drawing them together is comparing them.
a, b = "  function renderMap(){", "  /* ---------- table ---------- */"
assert script.count(a) == 1 and script.count(b) == 1
script = script[:script.index(a)] + r"""  // scanMiR reports classes the seed analyser never emits. They are binned
  // onto the existing three tick colours by strength, and everything
  // non-canonical gets a hollow tick - present, but the weakest thing the
  // model reports. A fifth hue would have to be validated for contrast and
  // colour-vision separation; a hollow mark needs neither.
  var SM_TICK = {"8mer":"t8", "wobbled 8mer":"t8", "g-bulged 8mer":"t8",
                 "7mer-m8":"t7m8", "7mer-a1":"t7a1", "7mer-A1":"t7a1",
                 "wobbled 7mer":"t7a1", "g-bulged 7mer":"t7a1",
                 "6mer":"t6", "6mer-m8":"t6", "6mer-a1":"t6",
                 "g-bulged 6mer":"t6"};
  function smTick(t){ return SM_TICK[t] || "tnc"; }

  function flashSite(k){
    // Clicking a row in the expanded table is a question about a place on
    // the transcript, so the answer is on the map. Bring the map into view
    // and mark the site for a few seconds - long enough to find it, short
    // enough not to sit there blinking.
    if (!k) return;
    var b = document.querySelector('#map [data-k="' + k + '"]');
    if (!b) return;
    var box = document.getElementById("map");
    (box.closest(".panel") || box).scrollIntoView({behavior: "smooth",
                                                   block: "center"});
    b.classList.remove("flash");
    void b.offsetWidth;                 // restart the animation
    b.classList.add("flash");
    setTimeout(function(){ b.classList.remove("flash"); }, 4500);
  }

  function flashTableSite(k){
    // The reverse question from flashSite: clicking a position on the map
    // asks "where is this stored record in the table?" - the answer is the
    // matching row in the gene's own expanded detail table (detailRow/
    // rawSites), further down the page below the map. That row already
    // gets a persistent highlight from the sitesel class once render() has
    // drawn it selected, so this only needs to bring it into view, not
    // animate it as well.
    if (!k) return;
    var row = document.querySelector('#results .sites [data-k="' + k + '"]');
    if (!row) return;
    row.scrollIntoView({behavior: "smooth", block: "center"});
  }

  function renderMap(){
    if (!sel || !TX[sel]){
      document.getElementById("map").innerHTML =
        '<p class="say mapnone">Select a gene in the table below to draw ' +
        'its binding map.</p>';
      document.getElementById("maphint").textContent = "";
      return;
    }
    var t = TX[sel], five = t.cds[0]-1, cds = t.cds[1]-t.cds[0]+1, three = t.len-t.cds[1];
    var maj = t.len>6000?2000:(t.len>3000?1000:400), min = maj/4, ruler = "";
    for (var p=0; p<=t.len; p+=min){
      var pc=(p/t.len)*100, M=(p%maj===0);
      ruler += '<span class="tick'+(M?" maj":"")+'" style="left:'+pc.toFixed(3)+'%"></span>';
      if (M) ruler += '<span class="tlab" style="left:'+pc.toFixed(3)+'%">'+
        (p===0?"0":(t.len>2000?(p/1000).toFixed(1).replace(/\.0$/,"")+"k":p))+"</span>";
    }
    var bar = '<div class="genebar"><span class="s5" style="width:'+((five/t.len)*100).toFixed(3)+'%"><b>5′UTR</b></span>'+
      '<span class="scd" style="width:'+((cds/t.len)*100).toFixed(3)+'%"><b>CDS</b></span>'+
      '<span class="s3" style="width:'+((three/t.len)*100).toFixed(3)+'%"><b>3′UTR</b></span></div>';

    var ss = seedOf(sel), rr = rhOf(sel), mm = smOf(sel);

    var seedLane = ss.length ? ss.map(function(s){
      var mid=((s[3]+s[4])/2/t.len)*100, k="seed|"+s[3];
      return '<button class="st'+(selSite===k?" sel":"")+'" data-k="'+k+'" style="left:'+mid.toFixed(3)+'%" '+
        'title="'+s[2]+" "+RL[s[1]]+" "+s[3]+"–"+s[4]+'"><i class="'+TICK_CLASS[s[2]]+'"></i>'+
        '<span class="lb">'+s[2]+"</span></button>";
    }).join("") : '<span class="none">no seed site on this transcript</span>';

    var rhLane = rr.length ? rr.map(function(r){
      var L=(r[2]/t.len)*100, W=Math.max(0.35,((r[3]-r[2]+1)/t.len)*100), k="rh|"+r[2];
      return '<button class="sd'+(r[4]<=-25?" strong":"")+(selSite===k?" sel":"")+'" data-k="'+k+'" '+
        'style="left:'+L.toFixed(3)+'%;width:'+W.toFixed(3)+'%" title="ΔG '+r[4].toFixed(1)+" · "+
        RL[r[1]]+" "+r[2]+"–"+r[3]+'"><span class="lb">'+r[4].toFixed(1)+"</span></button>";
    }).join("") : '<span class="none">no duplex below the −15 kcal/mol cutoff</span>';

    var smLane = mm.length ? mm.map(function(m){
      var mid=((m[3]+m[4])/2/t.len)*100, k="sm|"+m[3], cls=smTick(m[2]);
      // canonical sites are labelled; the non-canonical tail is drawn as
      // bare ticks, or a transcript with 26 of them becomes unreadable
      var lab = cls === "tnc" ? "" : '<span class="lb">'+m[2]+"</span>";
      return '<button class="st'+(selSite===k?" sel":"")+'" data-k="'+k+'" style="left:'+mid.toFixed(3)+'%" '+
        'title="'+m[2]+" "+(m[1]?RL[m[1]]:"")+" "+m[3]+"–"+m[4]+
        " · log Kd "+m[5].toFixed(3)+'"><i class="'+cls+'"></i>'+lab+"</button>";
    }).join("") : '<span class="none">no scanMiR site above the cutoff</span>';

    function lane(name, body, n){
      return '<div class="lanehead">'+name+'<span>'+n+" site"+(n===1?"":"s")+
        "</span></div>"+'<div class="lane"><div class="lanebody'+
        (n?"":" empty")+'">'+body+"</div></div>";
    }

    document.getElementById("map").innerHTML =
      '<div class="ruler">'+ruler+"</div>"+bar+
      lane("Seed analyser", seedLane, ss.length)+
      lane("RNAhybrid", rhLane, rr.length)+
      lane("scanMiR", smLane, mm.length);

    document.getElementById("maphint").textContent =
      sel + " · " + TX[sel].rs + " · " + t.len.toLocaleString() + " nt · " +
      ss.length + " seed site" + (ss.length===1?"":"s") + " · " +
      rr.length + " duplex" + (rr.length===1?"":"es") + " · " +
      mm.length + " scanMiR site" + (mm.length===1?"":"s");

    document.querySelectorAll("#map .st, #map .sd").forEach(function(b){
      b.addEventListener("click", function(){
        selSite = (selSite===b.dataset.k) ? null : b.dataset.k;
        render();
        flashTableSite(selSite);
      });
    });
  }

""" + script[script.index(b):]

# clicking a row in the expanded table jumps to that site on the map
a = """        selSite = (selSite===el.dataset.k) ? null : el.dataset.k;
        render();"""
assert script.count(a) == 1
script = script.replace(a, """        selSite = (selSite===el.dataset.k) ? null : el.dataset.k;
        render();
        flashSite(selSite);""", 1)


AGREE_CSS = """
  /* ---- tool agreement ----

  The UpSet list (5 tools - see agreement.py, VENN_MAX_SETS) still ranks by
  magnitude, so it keeps a one-hue ramp from the surface toward the accent.
  The Venn diagram (2-4 tools) is a different job: each circle IS a tool, so
  identity is the point, and identity needs one fixed hue per tool - never a
  magnitude ramp, which would say "how much" about something that is a
  "which". The five categorical hues (--agc-*) are validated for CVD
  separation and normal-vision separation as a set (dataviz skill,
  scripts/validate_palette.js, --pairs all - overlapping fills are the "any
  two marks can be neighbours" case, not the adjacent-only one). One pair
  (aqua/green, dark mode only) still sits under the normal-vision floor;
  that is why identity is never colour-alone here - every circle keeps its
  own fixed position in the standard 2/3/4-set layout (VENN_LAYOUT below)
  and its own row in the tools legend, so position and the legend carry
  identity and colour only reinforces it.

  Two ramps, each stepped against its own surface rather than flipped: the
  light one runs white to navy, the dark one near-black to light blue. On
  the top two steps the fill is too dark (light mode) or too light (dark)
  for ink at 3:1, so text sitting on those flips to --ag-on-deep. */
  :root, :root[data-theme="light"]{
    --ag-0:#ffffff; --ag-1:#eaf1f7; --ag-2:#cfe0ee; --ag-3:#9dc2dd;
    --ag-4:#5b92c2; --ag-5:#2e6da2; --ag-6:#12507e;
    --ag-on-deep:#ffffff;
    --agc-seed:#2a78d6; --agc-targetscan:#1baf7a; --agc-rnahybrid:#eda100;
    --agc-mirtarbase:#e34948; --agc-scanmir:#008300;
    --ag-chip-bg:#fcfcfb; --ag-chip-ink:#0b0b0b; --ag-chip-ring:rgba(11,11,11,.14);
  }
  @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
    --ag-0:#0e1113; --ag-1:#15242f; --ag-2:#1d3a52; --ag-3:#24506e;
    --ag-4:#35719a; --ag-5:#4b8fc0; --ag-6:#68a8dd;
    --ag-on-deep:#0e1113;
    --agc-seed:#3987e5; --agc-targetscan:#199e70; --agc-rnahybrid:#c98500;
    --agc-mirtarbase:#e66767; --agc-scanmir:#008300;
    --ag-chip-bg:#1a1a19; --ag-chip-ink:#ffffff; --ag-chip-ring:rgba(255,255,255,.16);
  }}
  :root[data-theme="dark"]{
    --ag-0:#0e1113; --ag-1:#15242f; --ag-2:#1d3a52; --ag-3:#24506e;
    --ag-4:#35719a; --ag-5:#4b8fc0; --ag-6:#68a8dd;
    --ag-on-deep:#0e1113;
    --agc-seed:#3987e5; --agc-targetscan:#199e70; --agc-rnahybrid:#c98500;
    --agc-mirtarbase:#e66767; --agc-scanmir:#008300;
    --ag-chip-bg:#1a1a19; --ag-chip-ink:#ffffff; --ag-chip-ring:rgba(255,255,255,.16);
  }

  /* the map now has a lane per tool, so each one is named */
  .lanehead{display:flex;justify-content:space-between;align-items:baseline;
            font-family:'IBM Plex Mono',monospace;font-size:10px;
            letter-spacing:.07em;text-transform:uppercase;color:var(--faint);
            margin:10px 0 3px}
  .lanehead span{letter-spacing:0;text-transform:none;font-size:10.5px}

  /* scanMiR's non-canonical sites: present, and the weakest thing it
     reports. Hollow rather than a fifth hue, which would need validating
     for contrast and colour-vision separation. */
  .tnc{background:transparent;box-shadow:inset 0 0 0 1.5px var(--faint)}

  /* a site arrived at from the table below: marked long enough to find,
     not long enough to nag */
  @keyframes siteflash{
    0%,100%{box-shadow:0 0 0 0 var(--sel-wash)}
    50%{box-shadow:0 0 0 5px var(--sel-wash)}
  }
  #map .flash{outline:2px solid var(--sel);outline-offset:2px;
              border-radius:2px;animation:siteflash .75s ease-in-out 6;z-index:5}
  @media (prefers-reduced-motion:reduce){
    #map .flash{animation:none}
  }

  /* the enriched-terms gene column: a preview, capped so one broad term
     cannot push the p-value column off the screen */
  .terms td.gsyms{font-size:11.5px;color:var(--muted);line-height:1.4;
                  max-width:30ch}
  .terms td.gsyms b{color:var(--ink);font-weight:600}
  .terms td.gsyms .more{color:var(--faint);white-space:nowrap}

  #agtools{flex-wrap:wrap;margin-bottom:10px}
  #agtools label{display:inline-flex;align-items:center;gap:5px}
  /* the checkbox row doubles as the colour legend - a swatch beside a name
     the reader already has to look at, rather than a second legend nobody
     reads (dataviz skill: identity is never colour-alone, so the swatch
     reinforces the checkbox's own text, it does not replace it) */
  .agswatch{width:10px;height:10px;border-radius:50%;flex:none;
            box-shadow:inset 0 0 0 1px var(--ag-chip-ring)}
  .agcap{max-width:none;margin:8px 0 0}

  /* ---- the Venn / single-circle figure ----

  Capped at 4 tools (agToolBoxes below enforces this in the picker): a Venn
  reads by its shape as much as its numbers, and a 5th circle needs ellipses
  and 31 regions, several too thin to read at all - see agreement.py's
  VENN_MAX_SETS and manifests/agreement_design.md. Sized generously (760px)
  because every region now carries a name-bearing chip, not just a number -
  and because the SVG's own coordinates (and every chip/label size within
  it) are untouched by this: a bigger box means everything in it, numbers
  included, renders physically larger, not a different layout. */
  .agvenn{display:block;width:100%;max-width:760px;height:auto;
          margin:10px auto 0;overflow:visible}
  .agshape{stroke:var(--surface);stroke-width:2px;fill-opacity:.55}
  /* multiply reads as classic Venny colour-mixing on a light surface; on a
     dark surface multiply only goes black, so overlaps lighten instead */
  @media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .agshape{
    mix-blend-mode:screen}}
  :root[data-theme="dark"] .agshape{mix-blend-mode:screen}
  :root, :root[data-theme="light"] .agshape{mix-blend-mode:multiply}
  @media (prefers-reduced-motion:no-preference){
    .agshape{transition:fill-opacity .15s}
  }
  .agshape.agdim{fill-opacity:.12}
  /* miRTarBase is evidence, not prediction (see agreement.py's module
     docstring) - a hatch on top of its own fill says so without spending a
     second hue, and survives print/forced-colours where hue does not
     (dataviz skill's texture channel) */
  .agshape.agevid-tex{fill:url(#agHatch);stroke:none;fill-opacity:.5;
                       pointer-events:none}

  /* the tool name printed just outside its own circle - the halo is a
     surface-coloured stroke under the fill (paint-order), not a computed
     contrast colour, so it stays legible over whatever is behind it in
     either theme without per-case tuning */
  .agsetlabel{font-family:'IBM Plex Mono',monospace;font-size:14.5px;
              font-weight:700;text-anchor:middle;pointer-events:none;
              paint-order:stroke fill;stroke:var(--surface);
              stroke-width:5.5px;stroke-linejoin:round}

  /* Every region is a small card, not just a number: percentage, the raw
     count, and - the part a reader used to have to trace overlapping
     circles to get - a dot per tool actually in this region, coloured like
     the tools legend above. A region nobody's gene ever landed in still
     gets a card at 0%, exactly like the ones that did; a Venn missing a
     slice reads as broken, not as "zero" (agreement.py now returns every
     combination, not just the non-empty ones). */
  .agchip{cursor:pointer}
  .agchip rect{fill:var(--ag-chip-bg);stroke:var(--ag-chip-ring);
               stroke-width:1px}
  .agchip .agchip-pct{fill:var(--ag-chip-ink);font-family:'IBM Plex Mono',monospace;
               font-weight:700;text-anchor:middle;dominant-baseline:central;
               pointer-events:none;font-variant-numeric:tabular-nums}
  .agchip .agchip-n{fill:var(--ag-chip-ink);opacity:.6;
               font-family:'IBM Plex Mono',monospace;font-weight:500;
               text-anchor:middle;dominant-baseline:central;
               pointer-events:none;font-variant-numeric:tabular-nums}
  .agchip .agchip-dot{pointer-events:none;stroke:var(--ag-chip-bg);
               stroke-width:.75px}
  .agchip:hover rect, .agchip:focus-visible rect{
    stroke:var(--sel);stroke-width:2px}
  .agchip:focus-visible{outline:none}
  .agcapnote{display:block;font-size:11px;color:var(--faint);margin:2px 0 0}

  /* ---- the UpSet-style list, five tools ---- */
  .agrows{display:grid;gap:3px;margin-top:4px}
  .agrow{display:grid;grid-template-columns:auto auto 1fr auto;gap:10px;
         align-items:center;font-size:12.5px;padding:3px 0;
         border:0;background:none;color:inherit;text-align:left;
         font-family:inherit;cursor:pointer;width:100%}
  .agrow:hover .aglbl{text-decoration:underline}
  .agrow .agdots{display:flex;gap:3px}
  .agrow .agdot{width:8px;height:8px;border-radius:50%;flex:none}
  .agrow .agdot.off{background:none!important;
                     box-shadow:inset 0 0 0 1px var(--faint)}
  .agrow .agn{font-variant-numeric:tabular-nums;color:var(--ink);
              min-width:8ch;text-align:right}
  .agrow .agn b{font-weight:600}
  .agrow .agn .agcount{color:var(--faint);font-weight:400}
  .agrow .aglbl{color:var(--muted);font-size:11.5px}
  .agbar{height:7px;border-radius:2px;background:var(--surface-2);
         position:relative;overflow:hidden}
  .agbar i{display:block;height:100%;border-radius:2px;background:var(--ag-4)}
  .agnone{color:var(--faint);font-size:12.5px;padding:6px 0}
  .agerr{color:var(--warn);font-size:12px}

  /* ---- the click-through detail box ---- */
  #agdetail{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
  .agdethead{display:flex;justify-content:space-between;align-items:baseline;
             flex-wrap:wrap;gap:8px 16px;margin-bottom:4px}
  .agdethead h3{font-size:13.5px;margin:0}
  .agdethead h3 b{font-variant-numeric:tabular-nums}
  .agdetclose{border:0;background:none;color:var(--faint);cursor:pointer;
              font-size:16px;line-height:1;padding:2px 4px}
  .agdetclose:hover{color:var(--ink)}
  .agdetnote{color:var(--muted);font-size:12px;margin:2px 0 10px;max-width:none}
  .agdetbar{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;
            margin-bottom:8px}
  .agdetbar .cols{display:flex;flex-wrap:wrap;gap:2px 10px;font-size:11px;
                  color:var(--muted)}
  .agdetbar .cols label{display:inline-flex;align-items:center;gap:3px}
  .agdetbtn{border:1px solid var(--line);background:var(--surface);
            color:var(--ink);border-radius:4px;font-size:11.5px;
            padding:3px 9px;cursor:pointer;font-family:inherit}
  .agdetbtn:hover{border-color:var(--muted)}
  .agdetbtn:disabled{opacity:.5;cursor:default}
  .agtable{width:100%;border-collapse:collapse;font-size:12px;margin-top:4px}
  .agtable th{text-align:left;font-weight:500;color:var(--faint);
              font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;
              padding:3px 8px;border-bottom:1px solid var(--line)}
  .agtable td{padding:3px 8px;border-bottom:1px solid var(--line-soft);
              vertical-align:top}
  .agtable tr.agtr{cursor:pointer}
  .agtable tr.agtr:hover td{background:var(--surface-2)}
  .agtable td.agsym{font-weight:600;color:var(--ink)}
  .agtable td.agcell{color:var(--muted);font-variant-numeric:tabular-nums;
                     white-space:nowrap}
  .agtable td.agcell .agmiss{color:var(--faint)}
  .agtable td.agmiss{color:var(--faint);text-align:center;padding:10px 8px}
  .agdetmore{font-size:11.5px;color:var(--muted);background:none;border:0;
             cursor:pointer;padding:6px 0;font-family:inherit}
  .agdetmore:hover{color:var(--ink);text-decoration:underline}
  .agdetstat{font-size:11.5px;color:var(--faint);margin-top:6px}
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
    <div class="mh-inner">
      <div class="brand-row">
        <div class="brand-name-col">
          <h1 id="title">&nbsp;</h1>
          <p class="maker">An Epigen-BioinfoLab Product</p>
        </div>
        <span class="kicker" id="kicker"></span>
      </div>
      <p class="sub2line" id="subtitle"></p>
      <p class="sub" id="tagline"></p>
    </div>
    <nav class="navrow" id="navRow">
      <button type="button" class="navitem" data-target="querybox">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 11l9-7 9 7"/><path d="M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9"/></svg>
        New Search</button>
      <button type="button" class="navitem" data-target="querybox">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        Query</button>
      <button type="button" class="navitem" data-target="mapsection" data-gate="results" disabled>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        Binding Map</button>
      <button type="button" class="navitem" data-target="resulttable" data-gate="results" disabled>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="10" y1="4" x2="10" y2="20"/></svg>
        The Result Table</button>
      <button type="button" class="navitem" data-target="agree" data-gate="results" disabled>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        Tool Agreement</button>
      <button type="button" class="navitem" data-target="enrich" data-gate="results" disabled>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20 C4 12,10 12,10 6"/><circle cx="10" cy="4" r="2"/><path d="M20 20 C20 14,15 14,15 9"/><circle cx="15" cy="7" r="2"/></svg>
        Pathway Analysis</button>
      <button type="button" class="navitem" data-target="netbox" data-gate="results" disabled>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="2.4"/><circle cx="5" cy="19" r="2.4"/><circle cx="19" cy="19" r="2.4"/><line x1="12" y1="7.4" x2="6.4" y2="17"/><line x1="12" y1="7.4" x2="17.6" y2="17"/><line x1="7.4" y1="19" x2="16.6" y2="19"/></svg>
        Target Network</button>
      <button type="button" class="navitem" data-select=".toolkey">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="7.5" r="0.6" fill="currentColor"/></svg>
        How The Tool Works</button>
      <button type="button" class="navitem" data-select=".notes">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2h9l5 5v15H6z"/><polyline points="15 2 15 7 20 7"/></svg>
        How To Read This Page</button>
    </nav>
  </header>

  <section class="panel" id="querybox">
    <h2>New Search<em></em></h2>
    <div class="panel-body">
      <form class="qform" id="qform">
        <label class="f f-sp"><span>Organism</span>
          <select id="f_species"></select></label>
        <label class="f"><span>miRNA</span>
          <input type="text" id="f_mirna" placeholder="hsa-miR-21-5p or MIMAT0000076" autocomplete="off"></label>
        <label class="f"><span>Genes (optional)</span>
          <input type="text" id="f_genes" placeholder="empty = whole transcriptome" autocomplete="off"></label>
        <div class="fgroup" id="f_tools"><span>Tools</span></div>
        <button class="go" id="runbtn" type="submit" disabled>Run</button>
        <span class="say" id="toolhint">Select at least one analysis method.</span>
      </form>
      <div class="notice spnotice" id="f_spnotice" hidden></div>
      <div class="notice err" id="qerr" hidden></div>
    </div>
  </section>

  <section class="panel" id="runbox" hidden>
    <h2>Running<em id="runjob"></em></h2>
    <div class="panel-body" id="runlist"></div>
  </section>

  <div id="guidesPreRun"></div>

  <div id="results" hidden>

    <div class="notice" id="prov"></div>
""" % (style, EXTRA_CSS + REDESIGN_CSS + EXPORT_CSS + NETWORK_CSS + POLISH_CSS
        + AGREE_CSS + """
/* Organism picker. The select inherits the form's own field styling;
   only what has no existing equivalent is defined here. */
.qform .f-sp select{font:inherit;padding:.45rem .5rem;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--ink);min-width:13rem}
/* A tool with no data for the chosen organism is dimmed AND disabled,
   never hidden: someone looking for TargetScan should find it and read
   why it cannot run, not wonder where it went. */
.toolpick .tp-off{opacity:.45}
.toolpick .tp-off .tps{font-style:italic}
.spnotice{line-height:1.6}
.spnotice ul.splinks{margin:.5rem 0 0;padding-left:1.1rem}
.spnotice ul.splinks li{margin:.25rem 0}
.spnotice code{font-size:.92em;word-break:break-all}
/* Upload form. Hidden until the user picks Other organism. */
.upform{display:grid;gap:.7rem;max-width:34rem}
.upform label{display:grid;gap:.25rem;font-size:13px;color:var(--muted)}
.upform input[type=text]{font:inherit;font-size:14px;padding:.45rem .5rem;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--ink)}
.upform input[type=file]{font-size:13px}
.upform .hint{font-size:12px;color:var(--muted);line-height:1.5}
.upbtn{font:inherit;font-size:14px;font-weight:600;padding:.5rem .9rem;border:0;border-radius:6px;background:var(--accent);color:#fff;cursor:pointer;justify-self:start}
.upbtn[disabled]{opacity:.5;cursor:default}
.upstat{font-size:13px;line-height:1.6}
.upstat.bad{color:#b3261e}
.upstat.good{color:#1e6b3a}
""")

TAIL_JS = r"""
  /* ================== live data ================== */

  function el(id){ return document.getElementById(id); }

  /* "How The Tool Works" and "How To Read This Page" are reference
     material a first-time user should be able to reach before they've run
     anything, not just after - but once a result exists they belong back
     at the bottom, beside Target Network, where they've always lived. So
     the two sections physically move: up beside New Search while #results
     is hidden (nothing to show yet), back down to their usual spot the
     moment a job's results are on screen. #guidesPreRun and #guidesHome
     are the two fixed anchors that mark those spots. */
  function positionGuides(preRun){
    // The masthead's links to everything below #results (Binding Map, the
    // table, Tool Agreement, Pathway Analysis, Target Network) are real
    // <button disabled> elements while there's nothing there to jump to -
    // gated here, the one place that already tracks whether #results is
    // showing.
    document.querySelectorAll('.navitem[data-gate="results"]').forEach(function(b){
      b.disabled = preRun;
    });
    var tk = document.querySelector(".toolkey"),
        nt = document.querySelector(".notes"),
        anchor = el(preRun ? "guidesPreRun" : "guidesHome");
    if (!tk || !nt || !anchor) return;
    anchor.parentNode.insertBefore(tk, anchor.nextSibling);
    tk.parentNode.insertBefore(nt, tk.nextSibling);
  }
  positionGuides(true);

  // Each section link scrolls to its target rather than navigating - the
  // whole page is one document. .toolkey/.notes move around (positionGuides
  // above), so their targets are looked up by selector at click time, never
  // cached, and always land on wherever the deck currently sits. Centered
  // rather than pinned to the top, so the section you asked for is the one
  // sitting in the middle of the screen, not a sliver at the very edge.
  document.querySelectorAll(".navitem").forEach(function(b){
    b.addEventListener("click", function(){
      var t = b.dataset.target ? el(b.dataset.target)
            : document.querySelector(b.dataset.select);
      if (t) t.scrollIntoView({behavior: "smooth", block: "center"});
    });
  });

  function jsonOrThrow(r){
    return r.json().then(function(b){
      if (!r.ok) throw (b && b.detail) ? b.detail : b;
      return b;
    });
  }
  function api(path){
    if (CURSP && /^\/(genes|mirnas)\//.test(path))
      path += (path.indexOf("?") < 0 ? "?" : "&") +
              "species=" + encodeURIComponent(CURSP);
    return fetch(path).then(jsonOrThrow);
  }
  function post(path, body){
    return fetch(path, {method: "POST", headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(body)}).then(jsonOrThrow);
  }

  var TOOLMETA = {}, MIRINFO = null, JOBID = null, JOBST = null, POLL = null;
  var SPECIES = [], TOOLS = [], CURSP = "human";
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

  /* ---------- panels ---------- */
  var TOOLLABEL = {seed: "Seed analyser", rnahybrid: "RNAhybrid",
                   targetscan: "TargetScan", mirtarbase: "miRTarBase",
                   scanmir: "scanMiR", "ml model": "ML model"};
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
    TX = {}; SEED = []; RH = []; TS = {}; MT = {}; SMS = []; GENES = [];
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
      } else if (r.tool === "scanmir"){
        SMS.push([r.symbol, r.region, r.site_type, r.pos_start, r.pos_end,
                  r.score]);
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
    // Returned so a caller that needs to act only once the table has
    // actually been repainted - focusGene()'s scroll, in particular - can
    // chain onto it instead of firing immediately against stale content.
    return api("/jobs/" + JOBID + "/genes?sort=" + PAGE.sort +
        "&limit=" + PAGE.limit + "&offset=" + PAGE.offset +
        (PAGE.gene ? "&gene=" + encodeURIComponent(PAGE.gene) : "") +
        (PAGE.q ? "&q=" + encodeURIComponent(PAGE.q) : ""))
      .then(function(p){
        PAGE.total = p.total_genes;
        applyData(p);
        el("results").hidden = false;
        el("runbox").hidden = true;
        positionGuides(false);
        render();
        pager();
        gsBoxes();
        netReload();
        agreeLoad();
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
    positionGuides(true);
    MIRINFO = null;
    api("/mirnas/" + encodeURIComponent(mir))
      .then(function(m){ MIRINFO = m; })
      .catch(function(){ /* the POST below reports the real error */ })
      .then(function(){
        return post("/jobs", {mirna: mir,
                              species: CURSP,
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

  // Shared by the small "← all genes" link and the big banner's own button -
  // both undo the exact same PAGE.gene/PAGE.q filter the exact same way.
  function clearGeneFocus(){
    PAGE.gene = null; PAGE.q = ""; el("geneq").value = "";
    el("geneqx").hidden = true; PAGE.offset = 0; loadPage();
  }

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
    // The big banner is narrower than that: PAGE.q can match many genes,
    // and "showing X only" would be false for all of them. It only ever
    // means what it says for a single-gene focus.
    var gb = el("genebanner");
    if (gb){
      gb.hidden = !PAGE.gene;
      if (PAGE.gene){
        var sym = el("genebannersym");
        if (sym) sym.textContent = PAGE.gene;
      }
    }
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
      '<button type="button" class="expprimary" data-scope="view" ' +
      'data-fmt="xlsx">Excel</button>' +
      '<button type="button" data-scope="view" data-fmt="tsv">TSV</button>' +
      '</div>' +
      '<div class="exprow"><span>Whole job</span>' +
      '<button type="button" class="expprimary" data-scope="all" ' +
      'data-fmt="xlsx">Excel</button>' +
      '<button type="button" data-scope="all" data-fmt="tsv">TSV</button>' +
      '</div>' +
      '<p class="exphint">Excel opens as a formatted, ready-to-read table. ' +
      'TSV is plain text for R or pandas — it will open in Excel too, but ' +
      'unstyled and one row per stored record, so a job with several tools ' +
      'looks sparse.</p>' +
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
    el("ungene").addEventListener("click", clearGeneFocus);

    // A prominent banner, not just the small "N only" text already in the
    // pager line - clicking a gene from the agreement diagram (or the
    // pathway panel, or the network view) filters this table down to one
    // row, and a reader landing here mid-scroll has no other way to tell
    // that what they are looking at is a single gene, not the whole table.
    // Sits directly above the table itself, inside #results, so it is the
    // first thing in view when focusGene() scrolls there.
    var tw = document.querySelector("#results .tablewrap");
    if (tw && tw.parentNode && !el("genebanner")){
      var gb = document.createElement("div");
      gb.id = "genebanner";
      gb.className = "genebanner";
      gb.hidden = true;
      gb.innerHTML = "Showing <b id=\"genebannersym\"></b> only" +
        " <button type=\"button\" class=\"linkbtn\" id=\"genebannerx\">" +
        "show all genes</button>";
      tw.parentNode.insertBefore(gb, tw);
      el("genebannerx").addEventListener("click", clearGeneFocus);
    }

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

  // Whether the enrichment currently shown (or about to be requested) came
  // from a Tool Agreement region click rather than this panel's own
  // tick-boxes. When true the boxes/regions/count are faded, because they
  // were never read for that run and would otherwise read as if they had
  // been. Cleared the instant the user genuinely touches a filter (a real
  // DOM event, not the programmatic gsChanged() call every table reload
  // already makes) or presses "Run GO and KEGG" themselves - either one
  // means the panel and whatever is showing below agree again.
  var GS_FROM_REGION = false;
  function gsSetSource(fromRegion){
    GS_FROM_REGION = !!fromRegion;
    el("enrich").classList.toggle("gs-external", GS_FROM_REGION);
    el("gsextnote").hidden = !GS_FROM_REGION;
  }

  function gsChanged(evt){
    if (evt) gsSetSource(false);
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
    gsSetSource(false);
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
      " were tested against a background of " +
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
      el("termbody").innerHTML = '<tr><td colspan="5">' +
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
    function termSymbols(t){
      // The term's own driver genes, not the whole list. Searching by gene
      // is only useful if you can see which gene matched, so a match is
      // pulled to the front rather than left buried at position 40.
      var syms = String(t.genes || "").split("/").filter(Boolean);
      var q = (ENRQ || "").toUpperCase();
      if (q) syms.sort(function(a, b){
        var am = a.toUpperCase().indexOf(q) >= 0,
            bm = b.toUpperCase().indexOf(q) >= 0;
        return am === bm ? 0 : (am ? -1 : 1);
      });
      var SHOWN = 6;
      var head = syms.slice(0, SHOWN).map(function(x){
        return q && x.toUpperCase().indexOf(q) >= 0
          ? "<b>" + esc(x) + "</b>" : esc(x);
      }).join(", ");
      // the full list is one click away in the expanded row, so the cell
      // stays a preview rather than a wall
      return head + (syms.length > SHOWN
        ? '<span class="more"> +' + (syms.length - SHOWN) + " more</span>" : "");
    }

    el("termbody").innerHTML = rows.length ? rows.map(function(t, i){
      return '<tr class="t" data-i="' + i + '">' +
        '<td class="caret">\u25b8</td>' +
        "<td>" + esc(t.description) +
        '<span class="tid">' + esc(t.term_id) + "</span></td>" +
        '<td class="num">' + t.k_in_term_and_list +
        (t.k_in_term_and_list === 1 ? " gene" : " genes") + "</td>" +
        '<td class="gsyms">' + termSymbols(t) + "</td>" +
        '<td class="num">' + t.p_adjust.toExponential(1) + "</td></tr>";
    }).join("") : ('<tr><td colspan="5">' + (run.status !== "done"
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
    // Waits for the table to actually hold this gene's row before scrolling
    // to it - firing scrollIntoView immediately, against whatever was on
    // screen before this fetch resolved, is what used to land the reader on
    // #results' own first child instead: the Binding map panel sits above
    // the results table inside that same div (see layout-source.html), so
    // scrolling to "the top of #results" and scrolling to "the results
    // table" were never the same thing. It also targets the table itself,
    // not the whole #results div, for exactly that reason.
    loadPage().then(function(){
      var target = document.querySelector("#results .tablewrap") ||
                   el("results");
      target.scrollIntoView({behavior: "smooth", block: "start"});
    });
  }

  /* ---------- organism ----------
     One control drives three things: which transcriptome is searched,
     which miRBase prefix a bare name is completed with, and which
     tools have data to run. It is built from GET /species rather than
     from a list in this page, so the set of organisms lives in exactly
     one place (src/species.py) and cannot drift. */

  var TOOLTITLE = {seed: "Seed Analysis", rnahybrid: "RNAhybrid",
                   targetscan: "TargetScan", mirtarbase: "miRTarBase",
                   scanmir: "scanMiR"};

  function spesc(s){
    return String(s == null ? "" : s).replace(/&/g, "&amp;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function curSpecies(){
    for (var i = 0; i < SPECIES.length; i++)
      if (SPECIES[i].key === CURSP) return SPECIES[i];
    return null;
  }

  // The full sentence stays in the label's title attribute; this is
  // only what fits on one line beside the tool's name.
  function shortWhy(why){
    if (/not loaded/i.test(why)) return "not loaded in this installation";
    if (/no standalone/i.test(why)) return "not loaded in this installation";
    return "no data for this organism";
  }

  function renderTools(){
    var s = curSpecies(), reason = {};
    ((s && s.tools_unavailable) || []).forEach(function(u){
      reason[u.tool] = u.reason;
    });
    // An organism whose transcripts were never loaded has nothing to
    // search, so every box is off until its files are uploaded.
    var notLoaded = CURSP === "__upload__"
      ? "Upload an organism first."
      : (s && !s.loaded ? s.common + " transcripts are not loaded yet."
                        : null);
    el("f_tools").innerHTML = '<span>Tools</span><div class="toolpick">' +
      TOOLS.map(function(t){
        var why = notLoaded || reason[t.name];
        return '<label class="tp' + (why ? " tp-off" : "") + '"' +
          (why ? ' title="' + spesc(why) + '"' : "") + '>' +
          '<input type="checkbox" value="' + t.name + '"' +
          (why ? " disabled" : "") + '>' +
          '<span class="tpn">' + spesc(TOOLTITLE[t.name] || t.name) +
          "</span>" +
          '<span class="tps">' +
          spesc(why ? shortWhy(why) : (t.question || "")) +
          "</span></label>";
      }).join("") + "</div>";
    toolsChanged();
  }

  function speciesChanged(){
    var s = curSpecies(), n = el("f_spnotice");
    if (CURSP === "__upload__"){ showUploadForm(n); renderTools(); return; }
    if (!s) return;
    el("f_mirna").placeholder =
      "miRNA name or MIMAT accession (" + s.mirbase + " assumed)";
    el("f_genes").placeholder = s.loaded
      ? "empty = whole transcriptome (" + s.transcripts.toLocaleString() +
        " genes)"
      : "empty = whole transcriptome";
    if (s.loaded || !s.fasta_url){
      n.hidden = true;
    } else {
      // Both files, always. A cDNA FASTA alone carries no CDS
      // boundary, and without it scanMiR treats the whole transcript
      // as 3'UTR and the region filters have nothing to filter on.
      n.hidden = false;
      n.innerHTML =
        "<b>" + spesc(s.common) + "</b> is not loaded in this " +
        "installation. Download both files from Ensembl (" +
        spesc(s.assembly) + "), then upload them:" +
        '<ul class="splinks">' +
        '<li><a href="' + spesc(s.fasta_url) + '">' +
        '<code>' + spesc(s.files[0]) + '</code></a> &mdash; ' +
        'transcript sequences</li>' +
        '<li><a href="' + spesc(s.gtf_url) + '">' +
        '<code>' + spesc(s.files[1]) + '</code></a> &mdash; ' +
        'gene annotation, which carries the CDS boundaries</li></ul>';
    }
    renderTools();
  }

  function buildSpecies(){
    var sel = el("f_species");
    sel.innerHTML = SPECIES.map(function(s){
      return '<option value="' + spesc(s.key) + '"' +
        (s.key === CURSP ? " selected" : "") + ">" + spesc(s.common) +
        (s.loaded ? "" : " \u2014 not loaded") + "</option>";
    }).join("");
    // One more entry, for an organism we do not have.
    sel.innerHTML += '<option value="__upload__">Other organism \u2014 upload your own</option>';
    sel.addEventListener("change", function(){
      CURSP = sel.value;
      speciesChanged();
    });
    speciesChanged();
  }

  /* ---------- bring your own organism ----------
     Two files and a name. The GTF is required: a FASTA alone has no
     coding boundary, so regions and the ORF penalty would silently
     stop working. The name is optional and only buys enrichment. */

  var UPPOLL = null;

  function showUploadForm(n){
    n.hidden = false;
    n.innerHTML =
      '<div class="upform">' +
      '<div class="hint">Bring an organism miRPanel does not have. Download its cDNA FASTA and GTF from Ensembl, from the same release, and upload both here.</div>' +
      '<label>Name<input type="text" id="up_label" placeholder="My organism"></label>' +
      '<label>Scientific name (optional, needed for pathway analysis)<input type="text" id="up_latin" placeholder="e.g. Xenopus tropicalis"></label>' +
      '<label>Transcript sequences, cDNA FASTA<input type="file" id="up_fasta" accept=".gz,.fa,.fasta"></label>' +
      '<label>Annotation, GTF<input type="file" id="up_gtf" accept=".gz,.gtf"></label>' +
      '<button type="button" class="upbtn" id="up_go">Upload</button>' +
      '<div class="upstat" id="up_stat"></div>' +
      '</div>';
    el("up_go").addEventListener("click", startUpload);
  }

  function upSay(msg, cls){
    var s = el("up_stat");
    if (s){ s.className = "upstat " + (cls || ""); s.innerHTML = msg; }
  }

  function startUpload(){
    var fa = el("up_fasta").files[0], gt = el("up_gtf").files[0];
    if (!fa || !gt){ upSay("Both files are needed.", "bad"); return; }
    var fd = new FormData();
    fd.append("label", el("up_label").value || "Uploaded organism");
    fd.append("latin", el("up_latin").value || "");
    fd.append("fasta", fa);
    fd.append("gtf", gt);
    el("up_go").disabled = true;
    upSay("Sending " + Math.round((fa.size+gt.size)/1048576) + " MB...");
    fetch("/uploads", {method:"POST", body: fd})
      .then(jsonOrThrow)
      .then(function(u){
        upSay("Reading the files. This takes about a minute.");
        pollUpload(u.upload_id);
      })
      .catch(function(e){
        el("up_go").disabled = false;
        upSay("Upload failed. " + (e && e.message ? e.message : ""), "bad");
      });
  }

  function pollUpload(id){
    if (UPPOLL) clearInterval(UPPOLL);
    UPPOLL = setInterval(function(){
      api("/uploads/" + id).then(function(u){
        if (u.status === "ready"){
          clearInterval(UPPOLL); UPPOLL = null;
          upSay(u.n_transcripts.toLocaleString() + " transcripts read. " +
                "Ready to search.", "good");
          adoptUpload(u.species);
        } else if (u.status === "failed"){
          clearInterval(UPPOLL); UPPOLL = null;
          el("up_go").disabled = false;
          upSay(u.error || "The files could not be read.", "bad");
        }
      }).catch(function(){});
    }, 2000);
  }

  // Reload the organism list so the new one appears, then select it.
  function adoptUpload(key){
    api("/species").then(function(r){
      SPECIES = r.species || [];
      CURSP = key;
      buildSpecies();
    });
  }

  function boot(){
    wire();
    netWire();
    Promise.all([api("/about"), api("/tools"), api("/species")])
      .then(function(r){
      var about = r[0], tools = r[1].tools;
      SPECIES = r[2].species || [];
      CURSP = r[2]["default"] || "human";
      document.title = about.name;
      el("title").textContent = about.name;
      el("tagline").textContent = about.description;
      el("subtitle").textContent = about.subtitle || "";
      // the kicker was in the approved layout but never filled; the version
      // is the one true thing that belongs above the name
      el("kicker").textContent = about.version ? "Version " + about.version : "";
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
      // Rebuilt whenever the organism changes, not once at startup:
      // which tools have data depends on the species.
      TOOLS = tools;
      buildSpecies();
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
    // Light fills in three clearly separated hues - blue, orange, rose -
    // each with a deeper border of the same hue so the shape still reads at
    // small sizes. Light fills matter here because the labels sit on top of
    // the drawing: a dark node would swallow its own name.
    return {accent: v("--accent", "#1f4e79"), ink: v("--ink", "#15181d"),
            line: v("--line", "#e3e6ea"), muted: v("--muted", "#666f7a"),
            surface: v("--surface", "#ffffff"),
            mirbg: "#f0a19b", mirline: "#bd4a42",
            valbg: "#9cc7e8", valline: "#2c6fa5",
            predbg: "#f7dd82", predline: "#c29a1e",
            edge: "#9aa4ae", edgeshare: v("--accent", "#12507e")};
  }

  function netStyleNode(n, P){
    // Every label gets a white halo. Without it a link drawn across a name
    // makes the name unreadable, and on a force layout you cannot predict
    // which names a link will cross.
    var halo = {strokeWidth: 5, strokeColor: "#ffffff"};
    if (n.group === "mirna")
      return {shape: "diamond", size: 30,
              color: {background: P.mirbg, border: P.mirline,
                      highlight: {background: P.mirbg, border: P.ink}},
              font: {color: P.ink, size: 17, face: "Inter, system-ui",
                     vadjust: 6, strokeWidth: halo.strokeWidth,
                     strokeColor: halo.strokeColor}};
    // Validated is not a better prediction, it is a different kind of claim,
    // so it gets its own colour rather than a place on one scale.
    var on = n.group === "validated";
    return {shape: "dot",
            color: {background: on ? P.valbg : P.predbg,
                    border: on ? P.valline : P.predline,
                    highlight: {background: on ? P.valbg : P.predbg,
                                border: P.ink}},
            font: {color: P.ink, size: 14, face: "Inter, system-ui",
                   strokeWidth: halo.strokeWidth,
                   strokeColor: halo.strokeColor}};
  }

  function netHint(){
    return "<h4>Click a node or a link</h4>Nodes are genes; the diamond is " +
           "the miRNA. A solid link means a tool reported that target, and " +
           "a dotted link means two genes appear together in enriched terms.";
  }

  function drawNetwork(d){
    NETDATA = d;
    var P = netPalette();
    el("k1").style.background = P.mirbg;
    el("k1").style.border = "2px solid " + P.mirline;
    el("k2").style.background = P.valbg;
    el("k2").style.border = "2px solid " + P.valline;
    el("k3").style.background = P.predbg;
    el("k3").style.border = "2px solid " + P.predline;

    var nodes = d.nodes.map(function(n){
      var s = netStyleNode(n, P);
      s.id = n.id; s.label = n.label; s.value = n.value;
      s.title = n.group === "mirna"
        ? n.label + " · " + n.accession + " · " + n.n_targets + " targets"
        : n.label + " \u00b7 " + n.n_tools + " of " +
          ((d.meta && d.meta.n_tools_run) || n.n_tools) + " tools" +
          (n.strong_functional ? " · " + n.strong_functional +
           " strong functional experiments" : "");
      return s;
    });

    var edges = d.edges.map(function(e, i){
      var shared = e.kind === "shared_terms";
      return {id: "e" + i, from: e.from, to: e.to, value: e.value,
              title: e.title,
              // dashed rather than dotted, and 2px rather than 1: at
              // one pixel in near-white the link was invisible against the
              // panel, so the layer looked like it had not been drawn
              dashes: shared ? [6, 4] : false,
              width: shared ? 2 : undefined,
              // mid grey so the links carry structure without competing with
              // the coloured nodes or the labels drawn over them
              color: {color: shared ? P.edgeshare : P.edge,
                      highlight: P.mirline, opacity: 1},
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
      netRow("scanMiR log Kd", n.log_kd == null ? null :
             n.log_kd.toFixed(3) + (n.sm_site ? " \u00b7 " + nesc(n.sm_site) : "") +
             (n.n_sm > 1 ? " (best of " + n.n_sm + " sites)" : "")) +
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
      .then(function(d){
        // a failed request and a failed draw are different problems and must
        // not share a handler - one shared catch hid a thrown TypeError as
        // "unavailable" for three rounds of debugging once already
        try {
          drawNetwork(d);
        } catch (err) {
          console.error("network: draw failed", err);
          el("netbox").hidden = false;
          el("netstate").textContent = "could not be drawn";
          el("netinfo").textContent = (err && err.message) ||
            "see the console for details";
        }
      })
      .catch(function(e){
        console.warn("network: request failed", e);
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

AGREE_JS = r"""
  /* ================== tool agreement ==================

  The results table says what each tool found. This says how much the tools
  overlap, and which genes sit where they disagree: a real Venn diagram for
  2-4 tools (VENN_LAYOUT), an UpSet-style list for all five (agreement.py's
  VENN_MAX_SETS is the same cutoff the server used to pick a.display).

  Every number is computed over the same filtered rows the table is showing,
  and the caption states both the filters and the membership rule. A figure
  whose numbers quietly disagree with the table above it reads as a bug even
  when both are right. */

  var AGREE = {all: null, picked: null, data: null, detail: null};
  var AGREE_LAST_KEY = null;

  // Fixed order, fixed colour, never cycled - the CVD-safety mechanism the
  // dataviz skill requires for a categorical palette. A tool's colour and
  // its position in this list do not change when other tools are ticked or
  // unticked, so "seed is blue" stays true across every render.
  var CANON = ["seed", "targetscan", "rnahybrid", "mirtarbase", "scanmir"];
  // The agreement figure's own default, independent of tool run order: one
  // evidence source plus two independent predictors, rather than "whichever
  // tools happen to run first" or "everything, until that hits the 4-cap".
  var DEFAULT_PICK = ["mirtarbase", "rnahybrid", "scanmir"];
  var TOOLHUE = {seed: "seed", targetscan: "targetscan", rnahybrid: "rnahybrid",
                mirtarbase: "mirtarbase", scanmir: "scanmir"};

  /* Every shape and every region-label position below was computed, not
     eyeballed: a dense grid of points was tested against each candidate
     layout of circles/ellipses, bucketed by which shapes contain each point,
     and the bucket's own mean position kept as that region's label anchor -
     which is also how "does every region actually have a visible area" was
     checked (four congruent ellipses cannot be fully 4-fold symmetric and
     still show a real Venn diagram; the search kept the layout whose
     smallest of the 15 regions was largest). See manifests/agreement_design.md
     for the search and the parameters it kept. Region keys are a bitmask
     over this layout's own shape letters A/B/C/D, assigned to the picked
     tools in CANON order - never to a fixed tool, since any 2-4 of the five
     can be picked. */
  // vb carries a 40-unit margin beyond the shapes on every side (unrelated
  // to the grid-sampled shape/centroid coordinates, which are untouched) -
  // room for the tool-name label that now sits just outside each circle.
  var VENN_LAYOUT = {
    1: {vb: [-40, -40, 320, 320],
       shapes: {A: {type: "circle", cx: 120, cy: 120, r: 100}},
       centroids: {1: [120, 120]}},
    2: {vb: [-40, -40, 500, 380],
       shapes: {A: {type: "circle", cx: 175, cy: 150, r: 110},
                B: {type: "circle", cx: 255, cy: 150, r: 110}},
       centroids: {1: [126.6, 150], 2: [303.4, 150], 3: [215, 150]}},
    3: {vb: [-40, -40, 540, 460],
       shapes: {A: {type: "circle", cx: 200, cy: 170, r: 120},
                B: {type: "circle", cx: 280, cy: 170, r: 120},
                C: {type: "circle", cx: 240, cy: 240, r: 120}},
       centroids: {1: [134.9, 132.6], 2: [345.1, 132.6], 3: [240, 101.8],
                   4: [240, 314.7], 5: [160.6, 239.1], 6: [319.4, 239.1],
                   7: [240, 193.5]}},
    4: {vb: [-40, -40, 780, 640],
       shapes: {
         A: {type: "ellipse", cx: 330, cy: 280, rx: 276.81, ry: 110.26, rot: -45.05},
         B: {type: "ellipse", cx: 239.84, cy: 280, rx: 276.81, ry: 110.26, rot: -51.32},
         C: {type: "ellipse", cx: 370, cy: 280, rx: 276.81, ry: 110.26, rot: 45.05},
         D: {type: "ellipse", cx: 460.16, cy: 280, rx: 276.81, ry: 110.26, rot: 51.32}},
       centroids: {1: [389.1, 266.0], 2: [129.0, 346.5], 3: [201.6, 379.6],
                   4: [310.9, 266.0], 5: [350.0, 367.0], 6: [227.9, 178.3],
                   7: [279.3, 278.1], 8: [571.0, 346.5], 9: [472.1, 178.3],
                   10: [350.0, 86.9], 11: [402.4, 126.6], 12: [498.4, 379.6],
                   13: [420.7, 278.1], 14: [297.6, 126.6], 15: [350.0, 207.8]}}
  };
  var LETTERS = ["A", "B", "C", "D"];

  // Chip size steps down as circles pack tighter (n=4's slivers are ~1% of
  // the figure - see the manifest), so the card never outgrows its region.
  var CHIP = {
    1: {w: 96, h: 58, pct: 16.5, n: 11, dotR: 3.6, dotGap: 10, pctY: -15, nY: 4, dotY: 20},
    2: {w: 68, h: 48, pct: 13.5, n: 9.5, dotR: 3.1, dotGap: 8.4, pctY: -13, nY: 3, dotY: 17},
    3: {w: 60, h: 44, pct: 12.5, n: 9, dotR: 2.8, dotGap: 7.6, pctY: -12, nY: 2, dotY: 15.5},
    4: {w: 50, h: 38, pct: 11, n: 8, dotR: 2.3, dotGap: 6.4, pctY: -10, nY: 1.5, dotY: 13}
  };

  // Is (px,py) inside sh, inflated by margin on every side? Handles the
  // rotated-ellipse case by rotating the point into the shape's own local
  // frame first (the inverse of the SVG rotate() applied to draw it), so a
  // circle (rot=0) and both ellipse tilts share one test.
  function agPointInside(px, py, sh, margin){
    var rx = (sh.type === "circle" ? sh.r : sh.rx) + margin;
    var ry = (sh.type === "circle" ? sh.r : sh.ry) + margin;
    var rad = (sh.rot || 0) * Math.PI / 180;
    var dx = px - sh.cx, dy = py - sh.cy;
    var lx = dx * Math.cos(rad) + dy * Math.sin(rad);
    var ly = -dx * Math.sin(rad) + dy * Math.cos(rad);
    return (lx * lx) / (rx * rx) + (ly * ly) / (ry * ry) <= 1;
  }

  // Direction a shape's label walks outward along before any 2D search:
  // for a circle, straight out from the cluster centre; for the 4-ellipse
  // layout, out along the shape's OWN major axis, because two of the four
  // sit on the same side of the cluster centre (see VENN_LAYOUT's rot) and
  // straight-out-from-centre would start their labels the same way. No two
  // of the four share a tilt, so each shape's own axis is still a distinct
  // starting direction even then.
  function agLabelDir(sh, cx0, cy0){
    if (sh.type === "circle"){
      var dx = sh.cx - cx0, dy = sh.cy - cy0;
      var len = Math.sqrt(dx * dx + dy * dy) || 1;
      return {axx: dx / len, axy: dy / len, baseR: sh.r};
    }
    var rad = sh.rot * Math.PI / 180, ax = Math.cos(rad), ay = Math.sin(rad);
    var toward = (sh.cx - cx0) * ax + (sh.cy - cy0) * ay;
    var sign = toward < 0 ? -1 : 1;
    return {axx: ax * sign, axy: ay * sign, baseR: sh.rx};
  }

  // .agsetlabel is a fixed monospace font (IBM Plex Mono, 700, 14.5px), so
  // its box is measured once rather than read back from the DOM per label:
  // 8.8px/char advance, and - since the SVG y attribute is the text
  // BASELINE, not a centre - 13.4px of glyph above it and 3.1px below,
  // both matching a real rendered getBBox() to a fraction of a pixel. A
  // first version of this fix used a box symmetric around y instead, which
  // under-covered the taller top half enough to still let a real label
  // overlap a shape by several pixels in the tightly-packed 3-circle view.
  function agLabelSize(text){ return {w: text.length * 8.8, top: 13.5, bot: 3.5}; }

  // Is the label's whole box - not just its anchor point - clear of every
  // shape? A single-point test (the anchor only) is what a first version
  // of this fix used, and it was fine for the wide, sparse 4-ellipse
  // layout, but the 3-circle default view packs its circles far closer
  // (each pair's centres sit well inside the other's radius): a point
  // 9px off a circle's edge is still comfortably INSIDE that circle once
  // you account for the ~110px of text hanging off it either side of the
  // anchor. Corners plus edge midpoints catch a shape boundary cutting
  // through the box without needing full polygon clipping.
  function agLabelClear(px, py, size, shapes, margin){
    var hw = size.w / 2, top = size.top, bot = size.bot;
    var pts = [[px, py], [px - hw, py - top], [px + hw, py - top],
               [px - hw, py + bot], [px + hw, py + bot],
               [px - hw, py], [px + hw, py], [px, py - top], [px, py + bot]];
    for (var s = 0; s < shapes.length; s++){
      for (var k = 0; k < pts.length; k++){
        if (agPointInside(pts[k][0], pts[k][1], shapes[s], margin)) return false;
      }
    }
    return true;
  }

  // Where a shape's own name goes. Starts at the shape's own edge, along
  // its own axis, and searches outward - trying a handful of small angular
  // detours at each distance before going further out - for the nearest
  // point whose whole label box clears every shape's fill AND every
  // already-placed label's box. Nearest-first keeps a label close to its
  // own shape whenever possible; searching several angles at each distance
  // (not just the one straight-out ray) is what makes this different from
  // simply extending the old fixed +22px offset, and is what stops two
  // labels that must both retreat from an overlap from just chasing each
  // other outward along nearly-parallel rays without ever actually
  // separating - the failure mode a first version of this fix hit, pushing
  // labels off the edge of the figure entirely.
  var LABEL_ANGLES = [0, 9, -9, 18, -18, 28, -28, 40, -40, 55, -55];
  function agPlaceLabel(sh, dir, size, shapes, placed, vb){
    var baseAngle = Math.atan2(dir.axy, dir.axx);
    var maxDist = dir.baseR + 18 + 320;
    var hw = size.w / 2;
    for (var dist = dir.baseR + 18; dist <= maxDist; dist += 7){
      for (var ai = 0; ai < LABEL_ANGLES.length; ai++){
        var a = baseAngle + LABEL_ANGLES[ai] * Math.PI / 180;
        var px = sh.cx + Math.cos(a) * dist, py = sh.cy + Math.sin(a) * dist;
        // Every layout's viewBox already carries a 40-unit margin for
        // exactly this label band, but a label that has to detour a long
        // way around a crowded neighbour can still walk past it - check
        // the box against the frame it will actually be drawn in, not
        // just against the other shapes and labels.
        if (px - hw < vb[0] || px + hw > vb[0] + vb[2] ||
            py - size.top < vb[1] || py + size.bot > vb[1] + vb[3]) continue;
        if (!agLabelClear(px, py, size, shapes, 4)) continue;
        var clash = false;
        for (var p = 0; p < placed.length; p++){
          var q = placed[p];
          var dx = Math.abs(px - q.x), dy = Math.abs(py - q.y);
          var dyMin = py >= q.y ? (size.top + q.size.bot) : (size.bot + q.size.top);
          if (dx < (size.w + q.size.w) / 2 + 6 && dy < dyMin + 6){
            clash = true; break;
          }
        }
        if (!clash) return [px, py];
      }
    }
    // Every candidate in range failed (shouldn't happen at these n, but a
    // future layout change could pack tighter) - fall back to the plain
    // shape-only, anchor-only clearance so a label is always drawn
    // somewhere sane rather than not being placed at all.
    var dist2 = dir.baseR + 18, px2, py2, tries = 0;
    do {
      px2 = sh.cx + dir.axx * dist2; py2 = sh.cy + dir.axy * dist2;
      dist2 += 6; tries++;
    } while (tries < 60 && shapes.some(function(o){
      return agPointInside(px2, py2, o, 9); }));
    return [px2, py2];
  }

  var SVGNS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs){
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function agLabel(names){
    if (!names.length) return "no tool";
    if (names.length === 1) return toolLabel(names[0]) + " only";
    var nice = names.map(toolLabel);
    return nice.slice(0, -1).join(", ") + " and " + nice[nice.length - 1];
  }

  function agCaption(a){
    var f = a.filters || {}, bits = [];
    if (f.regions)
      bits.push(f.regions.length ? "regions " + f.regions.join(", ")
                                 : "every region box unticked");
    if (f.include_6mer === false) bits.push("seed 6mer sites excluded");
    if (f.q) bits.push("gene search “" + f.q + "”");
    var out = "A gene counts as found by a tool when that tool reported at " +
              "least one row for it";
    if (a.membership && a.membership.scanmir_canonical_only)
      out += ", except scanMiR, which counts canonical sites only — at " +
             "its default threshold it reports a site on most of the " +
             "transcriptome, so any-site membership would say nothing";
    out += ". " + (bits.length ? "Filters applied: " + bits.join("; ") + "."
                               : "No filters applied.");
    return out;
  }

  // Same three filters the results table itself applies (see exportRegions/
  // show6/PAGE.q) - so the diagram, the detail box and the table above it
  // can never quietly disagree about which rows they mean.
  function agFilterQS(){
    var p = [], regs = exportRegions();
    if (regs.length < 3) p.push("regions=" + regs.join(","));
    if (!show6) p.push("include_6mer=false");
    if (PAGE.q) p.push("q=" + encodeURIComponent(PAGE.q));
    return p;
  }

  // A Venn tops out at 4 circles (agreement.py's VENN_MAX_SETS - past that
  // it needs ellipses and 31 regions, several too thin to read). Rather
  // than fall back to a plain list once a job ran a 5th tool, the picker
  // itself refuses a 5th tick: disable whatever is left unchecked once 4
  // are checked, so the ceiling is visible, not just enforced.
  function agSyncToolCap(box){
    var boxes = [].slice.call(box.querySelectorAll("input"));
    var n = boxes.filter(function(b){ return b.checked; }).length;
    boxes.forEach(function(b){ b.disabled = !b.checked && n >= 4; });
    var note = el("agcapnote");
    if (note) note.hidden = n < 4;
  }

  function agToolBoxes(a){
    var box = el("agtools");
    if (box.dataset.built) return;
    box.dataset.built = "1";
    AGREE.all.forEach(function(name){
      var lab = document.createElement("label");
      var sw = document.createElement("span");
      sw.className = "agswatch";
      sw.style.background = "var(--agc-" + (TOOLHUE[name] || "seed") + ")";
      var cb = document.createElement("input");
      cb.type = "checkbox"; cb.value = name;
      cb.checked = !AGREE.picked || AGREE.picked.indexOf(name) !== -1;
      cb.addEventListener("change", function(){
        var checked = [].slice.call(box.querySelectorAll("input:checked"));
        if (checked.length > 4){
          // belt and braces: agSyncToolCap disables the box before this can
          // normally fire, but a screen reader or a fast double-tap can
          // still slip a change event through before the disable lands
          cb.checked = false;
          return;
        }
        AGREE.picked = checked.map(function(i){ return i.value; });
        agSyncToolCap(box);
        agCloseDetail();
        agreeLoad();
      });
      lab.appendChild(cb);
      lab.appendChild(sw);
      lab.appendChild(document.createTextNode(" " + toolLabel(name)));
      box.appendChild(lab);
    });
    if (AGREE.all.length > 4 && !el("agcapnote")){
      var note = document.createElement("span");
      note.id = "agcapnote";
      note.className = "agcapnote";
      note.hidden = true;
      note.textContent = "The Venn shows at most 4 tools at once — untick " +
        "one to add another.";
      box.parentNode.insertBefore(note, box.nextSibling);
    }
    agSyncToolCap(box);
  }

  /* Which tools this region includes, translated into a bitmask over the
     CURRENT render's own A/B/C/D assignment - not a fixed tool-to-letter
     map, since any 2-4 of the five tools can be the ones on screen. */
  function agCode(letterOf, inc){
    var code = 0;
    inc.forEach(function(t){
      var L = letterOf[t];
      if (L) code |= (1 << LETTERS.indexOf(L));
    });
    return code;
  }

  function agRenderVenn(a, picked){
    var n = picked.length, layout = VENN_LAYOUT[n];
    var letterOf = {}, toolOf = {};
    picked.forEach(function(t, i){ letterOf[t] = LETTERS[i]; toolOf[LETTERS[i]] = t; });

    var svg = svgEl("svg", {viewBox: layout.vb.join(" "), class: "agvenn",
                            role: "img",
                            "aria-label": "Venn diagram of " +
                              picked.map(toolLabel).join(", ")});
    var defs = svgEl("defs", {});
    var pat = svgEl("pattern", {id: "agHatch", width: 6, height: 6,
                                patternUnits: "userSpaceOnUse",
                                patternTransform: "rotate(45)"});
    pat.appendChild(svgEl("rect", {width: 6, height: 6,
                                   fill: "var(--agc-mirtarbase)",
                                   "fill-opacity": .18}));
    pat.appendChild(svgEl("line", {x1: 0, y1: 0, x2: 0, y2: 6,
                                   stroke: "var(--agc-mirtarbase)",
                                   "stroke-width": 2.4}));
    defs.appendChild(pat);
    svg.appendChild(defs);

    var shapes = LETTERS.slice(0, n).map(function(L){ return layout.shapes[L]; });
    var cx0 = shapes.reduce(function(s, sh){ return s + sh.cx; }, 0) / n;
    var cy0 = shapes.reduce(function(s, sh){ return s + sh.cy; }, 0) / n;

    LETTERS.slice(0, n).forEach(function(L){
      var sh = layout.shapes[L], tool = toolOf[L];
      var fill = "var(--agc-" + (TOOLHUE[tool] || "seed") + ")";
      var el2;
      if (sh.type === "circle"){
        el2 = svgEl("circle", {cx: sh.cx, cy: sh.cy, r: sh.r,
                               "class": "agshape", "data-tool": tool, fill: fill});
      } else {
        el2 = svgEl("ellipse", {cx: sh.cx, cy: sh.cy, rx: sh.rx, ry: sh.ry,
                                transform: "rotate(" + sh.rot + " " + sh.cx +
                                  " " + sh.cy + ")",
                                "class": "agshape", "data-tool": tool, fill: fill});
      }
      svg.appendChild(el2);
      // miRTarBase gets a hatch on top of its own fill, not instead of it -
      // it is still one of the sets, just a visually distinct kind of one
      // (see agreement.py: kind "evidence" vs "prediction").
      if (tool === "mirtarbase"){
        var tex = el2.cloneNode();
        tex.setAttribute("class", "agshape agevid-tex");
        tex.removeAttribute("fill");
        svg.appendChild(tex);
      }
    });

    // Every shape's own name, drawn in its own pass AFTER every shape is
    // already on the canvas - not interleaved one-label-per-shape as the
    // shapes themselves are added. With four big overlapping ellipses the
    // union of the later ones (C, D) can easily cover the label anchor of
    // an earlier one (A, B): interleaved, "Seed analyser" and "RNAhybrid"
    // painted before C/D existed and then sat underneath them, unreadable
    // regardless of the legibility halo. A label is now always the last
    // thing painted at its position, so it is always on top of every
    // shape's fill, whichever shapes happen to reach that point. Beyond
    // paint order, each label also walks outward until it clears every
    // shape's fill entirely, so a name sits in the open margin rather than
    // over anyone's colour, its own circle included - and, once placed,
    // any two labels that still overlap EACH OTHER (the two same-side
    // ellipses' own axes are only ~6 degrees apart, so far enough out they
    // converge) get nudged further apart below.
    var placed = [];
    LETTERS.slice(0, n).forEach(function(L){
      var sh = layout.shapes[L], tool = toolOf[L];
      var fill = "var(--agc-" + (TOOLHUE[tool] || "seed") + ")";
      var name = toolLabel(tool), size = agLabelSize(name), lp;
      if (n === 1){
        lp = [sh.cx, sh.cy - sh.r - 20];
      } else {
        lp = agPlaceLabel(sh, agLabelDir(sh, cx0, cy0), size, shapes, placed, layout.vb);
      }
      var lbl = svgEl("text", {x: lp[0], y: lp[1], class: "agsetlabel",
                               fill: fill});
      lbl.textContent = name;
      svg.appendChild(lbl);
      placed.push({x: lp[0], y: lp[1], size: size});
    });

    var chip = CHIP[n];
    a.regions.forEach(function(r){
      var code = agCode(letterOf, r["in"]);
      var pt = layout.centroids[code];
      if (!pt) return;  // a region with no tool in the current picked set
      // Empty regions still exist in the layout - the shape itself is still
      // drawn, still coloured, still where it should be - only the chip
      // (and its click target) is skipped, so a 4-tool figure isn't showing
      // a dozen "0% (0)" cards nobody asked to see. agreement.py still
      // returns every combination; this is display-only.
      if (!r.n) return;
      var g = svgEl("g", {class: "agchip", tabindex: "0", role: "button",
                          "aria-label": r.label + " — " + r.n +
                            " gene" + (r.n === 1 ? "" : "s") + " of the union, " +
                            r.pct + "%",
                          transform: "translate(" + pt[0] + "," + pt[1] + ")"});
      g.appendChild(svgEl("rect", {x: -chip.w / 2, y: -chip.h / 2,
                                   width: chip.w, height: chip.h, rx: 7}));
      var pct = svgEl("text", {class: "agchip-pct", y: chip.pctY,
                               style: "font-size:" + chip.pct + "px"});
      pct.textContent = r.pct + "%";
      g.appendChild(pct);
      var cnt = svgEl("text", {class: "agchip-n", y: chip.nY,
                               style: "font-size:" + chip.n + "px"});
      cnt.textContent = "(" + r.n + ")";
      g.appendChild(cnt);
      // One dot per tool in this exact region, in the same fixed colour as
      // its circle and its row in the tools legend - the answer to "how
      // many, and which" without having to trace overlapping shapes.
      var dotsW = (r["in"].length - 1) * chip.dotGap;
      r["in"].forEach(function(t, i){
        g.appendChild(svgEl("circle", {
          class: "agchip-dot", r: chip.dotR,
          cx: -dotsW / 2 + i * chip.dotGap, cy: chip.dotY,
          fill: "var(--agc-" + (TOOLHUE[t] || "seed") + ")"}));
      });
      g.addEventListener("click", function(){ agOpenDetail(a, r); });
      g.addEventListener("keydown", function(ev){
        if (ev.key === "Enter" || ev.key === " "){ ev.preventDefault(); agOpenDetail(a, r); }
      });
      svg.appendChild(g);
    });

    var fig = el("agfig");
    fig.innerHTML = "";
    fig.appendChild(svg);
    // Every chip can legitimately be skipped at once (every region empty
    // under the current filters) - say so explicitly rather than leaving a
    // diagram with shapes but no numbers on it, which reads as broken.
    if (!a.regions.some(function(r){ return r.n; })){
      var none = document.createElement("p");
      none.className = "agnone";
      none.textContent = "No gene was found by any of the selected tools " +
        "under these filters.";
      fig.appendChild(none);
    }
  }

  function agRenderUpset(a){
    var fig = el("agfig");
    fig.innerHTML = "";
    if (!a.regions.some(function(r){ return r.n; })){
      fig.innerHTML = '<p class="agnone">No gene was found by any of the ' +
                      'selected tools under these filters.</p>';
      return;
    }
    var max = 0;
    a.regions.forEach(function(r){ if (r.n > max) max = r.n; });
    var order = CANON.filter(function(t){
      return a.tools.some(function(x){ return x.tool === t; }); });
    var wrap = document.createElement("div");
    wrap.className = "agrows";
    a.regions.forEach(function(r){
      if (!r.n) return;  // same declutter as the Venn chips: skip empty rows
      var row = document.createElement("button");
      row.type = "button"; row.className = "agrow";
      row.title = "Show these genes";

      var dots = document.createElement("span");
      dots.className = "agdots";
      order.forEach(function(t){
        var d = document.createElement("span");
        var on = r["in"].indexOf(t) !== -1;
        d.className = "agdot" + (on ? "" : " off");
        if (on) d.style.background = "var(--agc-" + (TOOLHUE[t] || "seed") + ")";
        d.title = toolLabel(t) + (on ? "" : " — not in this region");
        dots.appendChild(d);
      });

      var n = document.createElement("span");
      n.className = "agn";
      n.innerHTML = "<b>" + r.pct + "%</b> <span class=\"agcount\">(" + r.n + ")</span>";

      var bar = document.createElement("span");
      bar.className = "agbar";
      var fill = document.createElement("i");
      fill.style.width = Math.max(2, (r.n / max) * 100) + "%";
      bar.appendChild(fill);

      var lbl = document.createElement("span");
      lbl.className = "aglbl";
      lbl.textContent = r.label;

      row.appendChild(dots); row.appendChild(n); row.appendChild(bar); row.appendChild(lbl);
      row.addEventListener("click", function(){ agOpenDetail(a, r); });
      wrap.appendChild(row);
    });
    fig.appendChild(wrap);
  }

  function agreeRender(a){
    if (!AGREE.all) AGREE.all = a.tools.map(function(t){ return t.tool; });
    // The default view is miRTarBase + RNAhybrid + scanMiR - one evidence
    // source and two independent predictors, picked over never showing
    // every tool at once by default: a job that ran more than these three
    // would otherwise default to all of them (straight past the 4-tool cap
    // the picker enforces once you touch it) or, worse, to whichever four
    // happen to sort first in CANON order. If none of the three ran, fall
    // back to that CANON-order cap instead of leaving the choice to chance.
    if (!AGREE.picked){
      var def = DEFAULT_PICK.filter(function(t){
        return AGREE.all.indexOf(t) !== -1; });
      if (!def.length && AGREE.all.length > 4){
        def = CANON.filter(function(t){
          return AGREE.all.indexOf(t) !== -1; }).slice(0, 4);
      }
      if (def.length && def.length < AGREE.all.length){
        AGREE.picked = def;
        agreeLoad();
        return;
      }
      // The job ran exactly this default set (or a subset of it, or none
      // of the three and four-or-fewer tools total) - what just came back
      // already answers it, no second round trip needed, but AGREE.picked
      // still has to be set so the checkboxes reflect it correctly.
      if (def.length) AGREE.picked = def;
    }
    AGREE.data = a;
    agToolBoxes(a);
    el("agstate").textContent = a.n_genes + " genes  ·  " +
      a.tools.map(function(t){
        return toolLabel(t.tool) + " " + t.n_genes + (t.is_evidence ? "*" : "");
      }).join("  ·  ");
    if (!a.n_genes){
      el("agfig").innerHTML = '<p class="agnone">No gene was found by any ' +
        'of the selected tools under these filters.</p>';
    } else if (a.display === "upset"){
      agRenderUpset(a);
    } else {
      var picked = CANON.filter(function(t){
        return a.tools.some(function(x){ return x.tool === t; }); });
      agRenderVenn(a, picked);
    }
    el("agcap").textContent = agCaption(a);
    el("agree").hidden = false;
    // a filter or tool change invalidates whatever region was open
    if (AGREE.detail) agCloseDetail();
  }

  function agreeLoad(){
    var qs = agFilterQS();
    if (AGREE.picked && AGREE.picked.length)
      qs.push("tools=" + AGREE.picked.join(","));
    var key = JOBID + "?" + qs.join("&");
    // loadPage() calls this on every reload - including ones that have
    // nothing to do with the agreement figure, like turning a page, sorting,
    // or focusing one gene in the results table - so that a real change to
    // the region/6mer/search filters this figure also reads is never
    // missed. But agreeRender() closes whatever region detail is open on
    // every render ("a filter or tool change invalidates it"), which used
    // to fire on those unrelated reloads too: click a gene inside an open
    // region's table, and the table you clicked in would vanish out from
    // under you. Skipping a request identical to the one already answered
    // fixes that without touching the real invalidation - a genuine filter
    // or tool change always produces a different key.
    if (key === AGREE_LAST_KEY && AGREE.data) return;
    AGREE_LAST_KEY = key;
    api("/jobs/" + JOBID + "/agreement" + (qs.length ? "?" + qs.join("&") : ""))
      .then(function(a){
        /* A render bug and a request the server refused are different
           failures and must not share a handler: catching both in one place
           once hid a thrown TypeError as "nothing to show" for three
           rounds of debugging. */
        try {
          agreeRender(a);
        } catch (err) {
          console.error("agreement: render failed", err);
          el("agfig").innerHTML = '<p class="agerr">This section could not ' +
            'be drawn. The console has the details.</p>';
          el("agree").hidden = false;
        }
      })
      .catch(function(err){
        console.warn("agreement: not available", err);
        AGREE_LAST_KEY = null;  // not answered - worth trying again next time
        el("agree").hidden = true;
      });
  }

  /* ---------------- the click-through detail box ---------------- */

  var AGDET_PAGE = 40;

  function agCloseDetail(){
    AGREE.detail = null;
    var box = el("agdetail");
    box.hidden = true;
    box.innerHTML = "";
  }

  function agGenesURL(region, limit, offset){
    var qs = agFilterQS();
    qs.push("in=" + region["in"].join(","));
    if (region.out && region.out.length) qs.push("out=" + region.out.join(","));
    qs.push("limit=" + limit, "offset=" + offset);
    return "/jobs/" + JOBID + "/agreement/genes?" + qs.join("&");
  }

  function agCellFor(g, tool){
    var d = g.tools[tool];
    if (!d) return '<span class="agmiss">—</span>';
    var bits = [];
    if (d.best_site_type) bits.push(esc(d.best_site_type));
    if (d.best_score != null) bits.push(Number(d.best_score).toFixed(2));
    if (d.status) bits.push(esc(d.status));
    if (d.n_sites > 1) bits.push("(" + d.n_sites + " sites)");
    return bits.length ? bits.join(" · ") : '<span class="agmiss">—</span>';
  }

  function agRenderGeneTable(region, cols){
    var st = AGREE.detail;
    var t = document.createElement("table");
    t.className = "agtable";
    var thead = "<thead><tr><th>Gene</th>" + cols.map(function(c){
      return "<th>" + esc(toolLabel(c)) + "</th>"; }).join("") + "</tr></thead>";
    var rows = st.genes.length ? st.genes.map(function(g){
      return '<tr class="agtr" data-sym="' + esc(g.symbol) + '"><td class="agsym">' +
        esc(g.symbol) + '</td>' + cols.map(function(c){
          return '<td class="agcell">' + agCellFor(g, c) + '</td>'; }).join("") +
        '</tr>';
    }).join("") : ('<tr><td colspan="' + (cols.length + 1) + '" class="agmiss">' +
      "No gene matched this exact combination under the current filters." +
      "</td></tr>");
    t.innerHTML = thead + "<tbody>" + rows + "</tbody>";
    t.querySelectorAll("tr.agtr").forEach(function(tr){
      tr.addEventListener("click", function(){ focusGene(tr.dataset.sym); });
    });
    var old = el("agdettable");
    old.innerHTML = "";
    old.appendChild(t);
    el("agdetmore").hidden = st.genes.length >= st.n_genes;
    el("agdetstat").textContent = st.genes.length + " of " + st.n_genes +
      " gene" + (st.n_genes === 1 ? "" : "s") + " shown";
  }

  function agLoadMoreGenes(region, cols){
    var st = AGREE.detail;
    api(agGenesURL(region, AGDET_PAGE, st.genes.length)).then(function(r){
      st.genes = st.genes.concat(r.genes);
      agRenderGeneTable(region, cols);
    }).catch(function(e){ console.warn("agreement: genes page failed", e); });
  }

  function agExportCSV(region){
    // Tab-separated, not comma: the same reason api.py's own _tsv() gives -
    // a gene description or a status string can carry a comma, and on a
    // machine whose regional settings use something other than comma as
    // the list separator, Excel opens a comma file as one giant column
    // regardless of quoting. A tab has neither problem, which is also why
    // this now shares an extension with the exports built server-side.
    function cell(v){
      if (v == null) return "";
      return String(v).replace(/[\t\r\n]/g, " ");
    }
    var st = AGREE.detail, cols = st.cols;
    api(agGenesURL(region, 20000, 0)).then(function(r){
      var head = ["Gene", "Entrez"].concat(cols.map(toolLabel));
      var lines = [head.join("\t")];
      r.genes.forEach(function(g){
        var row = [cell(g.symbol), cell(g.entrez)].concat(cols.map(function(c){
          var d = g.tools[c];
          if (!d) return "";
          var bits = [d.best_site_type, d.best_score, d.status]
            .filter(function(x){ return x != null; });
          return cell(bits.join(" / "));
        }));
        lines.push(row.join("\t"));
      });
      var blob = new Blob([lines.join("\n")],
        {type: "text/tab-separated-values"});
      var a2 = document.createElement("a");
      a2.href = URL.createObjectURL(blob);
      a2.download = "agreement_" + region["in"].join("+") + ".tsv";
      a2.click();
      URL.revokeObjectURL(a2.href);
    }).catch(function(e){ console.warn("agreement: export failed", e); });
  }

  function agRunEnrichment(region){
    var btn = el("agdetenrich");
    btn.disabled = true;
    btn.textContent = "Fetching genes…";
    // The full list - not just the shown page - is fetched here, lazily, on
    // the click that actually needs it: eagerly pulling every gene for
    // every region someone merely looks at would mean fetching up to
    // 20,000 rows just in case, for a button most clicks on this diagram
    // will never press.
    api(agGenesURL(region, 20000, 0)).then(function(full){
      btn.textContent = "Starting…";
      return fetch("/jobs/" + JOBID + "/enrichment", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({genes: full.genes.map(function(g){ return g.entrez; }),
                              included: region["in"], excluded: region.out || []})
      });
    }).then(function(r){
      return r.json().then(function(j){
        if (!r.ok) throw new Error((j.detail && j.detail.message) ||
                                   "the request was refused");
        return j;
      });
    }).then(function(j){
      el("enrich").hidden = false;
      gsSetSource(true);
      watchRun(j.run_id);
      el("enrich").scrollIntoView({behavior: "smooth", block: "start"});
    }).catch(function(e){
      btn.textContent = (e && e.message) || "could not start";
    }).then(function(){
      setTimeout(function(){
        btn.disabled = false; btn.textContent = "Run enrichment on these genes";
      }, 1500);
    });
  }

  function agOpenDetail(a, region){
    var box = el("agdetail");
    var cols = region["in"].slice();
    AGREE.detail = {region: region, genes: [], n_genes: region.n, cols: cols};
    box.hidden = false;
    box.innerHTML =
      '<div class="agdethead"><h3>' + esc(region.label) +
      ' — <b>' + region.n + '</b> gene' + (region.n === 1 ? "" : "s") +
      ' (' + region.pct + '%)</h3>' +
      '<button type="button" class="agdetclose" aria-label="Close">×</button></div>' +
      '<p class="agdetnote">' + esc(region.note) + '</p>' +
      '<div class="agdetbar">' +
      '<span class="cols">' + cols.map(function(c){
        return '<label><input type="checkbox" checked value="' + esc(c) +
          '"> ' + esc(toolLabel(c)) + '</label>'; }).join("") + '</span>' +
      '<button type="button" class="agdetbtn" id="agdetexport">Export table (TSV)</button>' +
      '<button type="button" class="agdetbtn" id="agdetenrich">Run enrichment on these genes</button>' +
      '</div>' +
      '<div id="agdettable"></div>' +
      '<button type="button" class="agdetmore" id="agdetmore" hidden>Show more genes</button>' +
      '<p class="agdetstat" id="agdetstat"></p>';

    box.querySelector(".agdetclose").addEventListener("click", agCloseDetail);
    box.querySelector("#agdetexport").addEventListener("click", function(){
      agExportCSV(region);
    });
    box.querySelector("#agdetenrich").addEventListener("click", function(){
      agRunEnrichment(region);
    });
    box.querySelectorAll(".cols input").forEach(function(cb){
      cb.addEventListener("change", function(){
        var on = [].slice.call(box.querySelectorAll(".cols input:checked"))
                    .map(function(i){ return i.value; });
        // keep table columns in the region's own tool order, not click order
        AGREE.detail.cols = region["in"].filter(function(t){
          return on.indexOf(t) !== -1; });
        agRenderGeneTable(region, AGREE.detail.cols);
      });
    });
    el("agdetmore").addEventListener("click", function(){
      agLoadMoreGenes(region, AGREE.detail.cols);
    });

    api(agGenesURL(region, AGDET_PAGE, 0)).then(function(r){
      AGREE.detail.genes = r.genes;
      AGREE.detail.n_genes = r.n_genes;
      agRenderGeneTable(region, cols);
    }).catch(function(e){
      box.innerHTML = '<p class="agerr">Could not load these genes. ' +
        'The console has the details.</p>';
      console.error("agreement: region_genes failed", e);
    });

    box.scrollIntoView({behavior: "smooth", block: "nearest"});
  }
"""


def _tail_with(extra):
    """Put `extra` inside TAIL_JS's IIFE, not after it.

    The page's whole script is wrapped in (function(){ "use strict"; ... })();
    so api, el, JOBID and toolLabel are private to it. Code appended after
    the closing brace lands in global scope - still callable by name from
    inside, because function declarations hoist to globalThis - and then
    throws "api is not defined" the first time it runs. That surfaced
    through showErr as a red box on the page with nothing in the console,
    which is a slow thing to debug. Hence this helper rather than a "+".
    """
    close = "\n})();\n"
    i = TAIL_JS.rindex(close)
    return TAIL_JS[:i] + "\n" + extra + TAIL_JS[i:]


OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HEAD + keep + """  </div>

  <p class="sources" id="sources"></p>

</div>

<script src="vendor/vis-network.min.js"></script>
<script>
""" + script + NETWORK_JS + _tail_with(AGREE_JS) + """</script>
</body>
</html>
""")
print("wrote", OUT, OUT.stat().st_size, "bytes")
