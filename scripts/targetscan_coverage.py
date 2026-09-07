"""How many human miRNAs actually get a TargetScan default prediction?"""
import csv, sqlite3, sys

SC = sys.argv[1] if len(sys.argv) > 1 else "data/raw/Summary_Counts.default_predictions.txt"
FI = "data/raw/miR_Family_Info.txt"
DB = "data/processed/mirna.db"

seeds_with_predictions = set()
with open(SC) as fh:
    next(fh)
    for line in fh:
        f = line.split("\t")
        if f[3] == "9606":
            seeds_with_predictions.add(f[2])
print("human seeds with predictions:", len(seeds_with_predictions))

acc_seed = {}
for r in csv.DictReader(open(FI), delimiter="\t"):
    if r["Species ID"] == "9606":
        acc_seed[r["MiRBase Accession"].strip()] = r["Seed+m8"].strip()

con = sqlite3.connect(DB)
ours = [a for (a,) in con.execute("SELECT accession FROM mirnas WHERE species='hsa'")]

covered = in_ts_no_pred = not_in_ts = 0
for a in ours:
    if a not in acc_seed:
        not_in_ts += 1
    elif acc_seed[a] in seeds_with_predictions:
        covered += 1
    else:
        in_ts_no_pred += 1

print("our human miRNAs        :", len(ours))
print("  have a prediction     :", covered)
print("  in TargetScan, no pred:", in_ts_no_pred)
print("  not in TargetScan     :", not_in_ts)
