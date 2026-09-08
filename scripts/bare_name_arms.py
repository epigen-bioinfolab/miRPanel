"""For unresolved bare names, how many have exactly one arm in Release 23?"""
import sqlite3

con = sqlite3.connect("data/processed/mirna.db")
names = {nm: c for nm, c in con.execute(
    "SELECT mirna_name, COUNT(*) FROM mirtarbase_evidence "
    "WHERE accession IS NULL GROUP BY mirna_name")}
r23 = {n: a for n, a in con.execute(
    "SELECT name, accession FROM mirnas WHERE species='hsa'")}

one = two = none = 0
rows_one = rows_two = rows_none = 0
examples = []
for nm, c in names.items():
    arms = [nm + s for s in ("-3p", "-5p") if nm + s in r23]
    if len(arms) == 1:
        one += 1; rows_one += c
        if len(examples) < 5:
            examples.append((nm, arms[0], c))
    elif len(arms) == 2:
        two += 1; rows_two += c
    else:
        none += 1; rows_none += c
print("exactly one arm in R23:", one, "names,", rows_one, "rows")
print("both arms in R23      :", two, "names,", rows_two, "rows")
print("no arm in R23         :", none, "names,", rows_none, "rows")
print("examples:", examples)
