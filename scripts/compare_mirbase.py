"""Compare human miRNAs between two miRBase mature.fa releases."""
from pathlib import Path

SPECIES = "hsa-"

def read_mature(path):
    """Return {accession: (name, sequence)} for one species from a miRBase mature.fa."""
    entries, name, acc, parts = {}, None, None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith(">"):
            if acc and name.startswith(SPECIES):
                entries[acc] = (name, "".join(parts))
            fields = line[1:].split()
            if len(fields) < 2:
                name, acc, parts = "", None, []
                continue
            name, acc, parts = fields[0], fields[1], []
        else:
            parts.append(line.strip())
    if acc and name.startswith(SPECIES):
        entries[acc] = (name, "".join(parts))
    return entries

def seed(seq):
    """Seed region, nucleotides 2-8, as DNA."""
    return seq.upper().replace("U", "T")[1:8]

old = read_mature("data/raw/mature_r22.fa")
new = read_mature("data/raw/mature_r23.fa")

both = set(old) & set(new)
gone = set(old) - set(new)
added = set(new) - set(old)
renamed = sorted(a for a in both if old[a][0] != new[a][0])
seq_changed = sorted(a for a in both if old[a][1] != new[a][1])
seed_changed = sorted(a for a in both if seed(old[a][1]) != seed(new[a][1]))

lines = [
    "Human miRNAs: miRBase Release 22 vs Release 23",
    "=" * 48,
    f"in Release 22 only          {len(old):>6}",
    f"in Release 23 only          {len(new):>6}",
    f"present in both             {len(both):>6}",
    f"removed in 23               {len(gone):>6}",
    f"new in 23                   {len(added):>6}",
    "-" * 48,
    f"renamed (same accession)    {len(renamed):>6}",
    f"sequence changed            {len(seq_changed):>6}",
    f"SEED changed                {len(seed_changed):>6}   <- the ones that matter",
    "=" * 48,
    "",
    "Examples of renaming:",
]
for a in renamed[:5]:
    lines.append(f"  {a}  {old[a][0]:<20} -> {new[a][0]}")

lines.append("")
lines.append("Examples of seed change:")
for a in seed_changed[:5]:
    lines.append(f"  {a}  {new[a][0]:<20} {seed(old[a][1])} -> {seed(new[a][1])}")

report = "\n".join(lines)
print(report)
Path("manifests/mirbase_22_vs_23_human.txt").write_text(report + "\n")
Path("manifests/seed_changed_accessions.txt").write_text("\n".join(seed_changed) + "\n")
