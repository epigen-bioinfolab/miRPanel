# -*- coding: utf-8 -*-
"""In a several-miRNA search the Query panel shows no mature sequence, no
seed, and claims the miRNA is not in TargetScan.

Each tab loads its own job, and a job record carries only the name and the
accession. MIRINFO is filled once, by the single-search flow, so on a tab
it is null and the panel falls back to those two fields. Look the miRNA up
when the panel needs more than the job has.

    python3 fix_mirinfo.py
    python3 scripts/build_page.py
"""

import ast
import shutil
from pathlib import Path

BP = Path("scripts/build_page.py")

PAIRS = [
    ("  var TOOLMETA = {}, MIRINFO = null, JOBID = null, JOBST = null, POLL = null;",
     "  var TOOLMETA = {}, MIRINFO = null, JOBID = null, JOBST = null, POLL = null;\n"
     "  // the miRNA whose details are already being fetched, so a redraw\n"
     "  // while the request is in flight does not ask again\n"
     "  var MIRFETCH = null;"),

    ("""  function fillPanels(){
    el("prov").textContent =""",
     """  function fillPanels(){
    // A job record holds the name and accession, nothing else. On a tab of
    // a several-miRNA search that is all we have, so the mature sequence,
    // the seed and the TargetScan family have to be looked up before the
    // panel can show them. Redraw once the answer arrives.
    var want = (JOBST && JOBST.params && JOBST.params.mirna_name) ||
               (MIR && MIR.name);
    if (want && !(MIR && MIR.seq && MIR.name === want) && MIRFETCH !== want){
      MIRFETCH = want;
      fetch("/mirnas/" + encodeURIComponent(want) + "?species=" +
            encodeURIComponent((JOBST && JOBST.species) || CURSP))
        .then(function(r){ return r.json(); })
        .then(function(m){
          if (!m || !m.sequence) return;
          MIRINFO = m;
          MIR = {name: m.name, acc: m.accession, seq: m.sequence, seed: m.seed,
                 family: m.targetscan ? m.targetscan.family : null,
                 cons: m.targetscan ? m.targetscan.conservation : null};
          fillPanels();
        })
        .catch(function(err){ console.warn("miRNA details: not available", err); });
    }

    el("prov").textContent ="""),

    ("    MIRINFO = null;", "    MIRINFO = null;\n    MIRFETCH = null;"),
]


def main():
    if not BP.exists():
        print("Run this from the project root.")
        return 1

    s = BP.read_text(encoding="utf-8")
    if "MIRFETCH" in s:
        print("Already fixed - nothing changed.")
        return 0

    bak = BP.with_suffix(BP.suffix + ".bak9")
    shutil.copy2(BP, bak)

    done, failed = [], []
    for old, new in PAIRS:
        n = s.count(old)
        if n == 1:
            s = s.replace(old, new)
            done.append(old.strip().splitlines()[0][:50])
        else:
            failed.append("found %d times: %s" % (n, old.strip().splitlines()[0][:50]))

    if len(done) < 3:
        print("\nFAILED - nothing changed:")
        for f in failed:
            print("  -", f)
        return 1

    BP.write_text(s, encoding="utf-8")

    try:
        ast.parse(BP.read_text(encoding="utf-8"))
    except SyntaxError as e:
        shutil.copy2(bak, BP)
        print("build_page.py would not parse (%s) - rolled back." % e)
        return 1

    print("Done:")
    for d in done:
        print("  -", d)
    print("""
Backup is scripts/build_page.py.bak9

Now run:
  python3 scripts/build_page.py""")
    return 0


raise SystemExit(main())
