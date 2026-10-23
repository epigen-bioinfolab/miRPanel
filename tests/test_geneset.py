"""Checks for the pathway-analysis gene selector.

    python scripts/test_geneset.py

Builds a small in-memory job with known answers, so every count below can
be verified by hand from the fixture at the top of the file.
"""
import sqlite3
import sys
sys.path.insert(0, "src")

import geneset

PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    print(("  ok    " if ok else "  FAIL  ") + label +
          ("" if ok else "   got %r, want %r" % (got, want)))


con = sqlite3.connect(":memory:")
con.execute("""CREATE TABLE results (job_id TEXT, entrez INT, symbol TEXT,
               region TEXT, tool TEXT, site_type TEXT, score REAL,
               low_confidence INT)""")

# gene 1  8mer in the 3'UTR, TargetScan conserved -0.50, rnahybrid -30, validated
# gene 2  8mer in the CDS,   TargetScan -0.10 not conserved
# gene 3  7mer-m8 3'UTR,     TargetScan conserved -0.40
# gene 4  6mer 3'UTR only
# gene 5  nothing but an rnahybrid duplex at -28
ROWS = [
    (1, "AAA", "3UTR", "seed", "8mer", None, 0),
    (1, "AAA", None, "targetscan", None, -0.50, 0),
    (1, "AAA", "3UTR", "rnahybrid", None, -30.0, 0),
    (1, "AAA", None, "mirtarbase", None, 12.0, 0),
    (2, "BBB", "CDS", "seed", "8mer", None, 0),
    (2, "BBB", None, "targetscan", None, -0.10, 1),
    (3, "CCC", "3UTR", "seed", "7mer-m8", None, 0),
    (3, "CCC", None, "targetscan", None, -0.40, 0),
    (4, "DDD", "3UTR", "seed", "6mer", None, 0),
    (5, "EEE", "3UTR", "rnahybrid", None, -28.0, 0),
]
con.executemany("INSERT INTO results VALUES ('J',?,?,?,?,?,?,?)", ROWS)
con.commit()


def n(**spec):
    return geneset.select(con, "J", spec)["count"]


print("site type ranking comes from the registry")
check("8mer alone", geneset.site_types("8mer"), ["8mer"])
check("7mer-m8 includes 8mer", geneset.site_types("7mer-m8"), ["8mer", "7mer-m8"])
check("any is every type", len(geneset.site_types("any")), 4)

print("one box at a time")
check("8mer sites", n(seed="8mer"), 2)                       # AAA, BBB
check("7mer-m8 or better", n(seed="7mer-m8"), 3)             # + CCC
check("any seed site", n(seed="any"), 4)                     # + DDD
check("TargetScan any", n(targetscan="any"), 3)              # AAA, BBB, CCC
check("TargetScan conserved", n(targetscan="conserved"), 2)  # AAA, CCC
check("context++ <= -0.45", n(targetscan=-0.45), 1)          # AAA
check("dG <= -29", n(rnahybrid=-29), 1)                      # AAA
check("dG <= -25", n(rnahybrid=-25), 2)                      # AAA, EEE
check("miRTarBase strong", n(mirtarbase="strong"), 1)        # AAA

print("regions apply to positional tools only")
check("8mer in the 3'UTR only", n(seed="8mer", regions=["3UTR"]), 1)   # AAA
check("8mer in the CDS only", n(seed="8mer", regions=["CDS"]), 1)      # BBB
check("TargetScan ignores the region filter",
      n(targetscan="any", regions=["CDS"]), 3)

print("AND and OR")
check("8mer AND conserved", n(seed="8mer", targetscan="conserved"), 1)      # AAA
check("8mer OR conserved", n(seed="8mer", targetscan="conserved",
                             match="any"), 3)                              # AAA,BBB,CCC
check("8mer AND dG<=-25", n(seed="8mer", rnahybrid=-25), 1)                # AAA
check("8mer OR dG<=-25", n(seed="8mer", rnahybrid=-25, match="any"), 3)    # +EEE
check("three boxes, AND", n(seed="8mer", targetscan="conserved",
                            mirtarbase="strong"), 1)

print("it says what it did")
r = geneset.select(con, "J", {"seed": "8mer", "targetscan": "conserved"})
check("sentence", r["sentence"],
      "1 gene with a 8mer site and a conserved TargetScan site")
check("nothing ticked", geneset.select(con, "J", {})["count"], 0)

print("bad input is refused")
for label, spec in (("unknown site type", {"seed": "9mer"}),
                    ("unknown region", {"seed": "8mer", "regions": ["INTRON"]}),
                    ("bad match", {"seed": "8mer", "match": "sometimes"})):
    try:
        geneset.select(con, "J", spec)
        check(label, "accepted", "rejected")
    except ValueError:
        check(label, "rejected", "rejected")

print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
