"""Parse the MANE GenBank flatfile and report on it. Writes nothing."""
import gzip, re
from statistics import median

GBFF = "data/raw/MANE.GRCh38.v1.5.refseq_rna.gbff.gz"
LOC = re.compile(r"^<?(\d+)\.\.>?(\d+)$")


def records(path):
    ver = length = None
    feat, seq, where = [], [], None
    with gzip.open(path, "rt") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("LOCUS"):
                length = int(line.split()[2])
                ver, feat, seq, where = None, [], [], None
            elif line.startswith("VERSION"):
                ver = line.split()[1]
            elif line.startswith("FEATURES"):
                where = "f"
            elif line.startswith("ORIGIN"):
                where = "s"
            elif line.startswith("//"):
                yield ver, length, "\n".join(feat), "".join(seq).upper()
            elif where == "f":
                feat.append(line)
            elif where == "s":
                seq.append("".join(c for c in line if c.isalpha()))


def q(text, name):
    m = re.search('/%s="([^"]+)"' % name, text)
    return m.group(1) if m else ""


n = ok = nocds = badlen = baddiv = badloc = 0
u5, cl, u3 = [], [], []
pdcd4 = None

for ver, length, feat, seq in records(GBFF):
    n += 1
    flat = re.sub(r"\n {21}", " ", feat)
    sym = q(flat, "gene")
    syn = q(flat, "gene_synonym")
    if len(seq) != length:
        badlen += 1
    m = re.search(r"^     CDS\s+(\S+)", feat, re.M)
    if not m:
        nocds += 1
        continue
    loc = LOC.match(m.group(1))
    if not loc:
        badloc += 1
        continue
    s, e = int(loc.group(1)), int(loc.group(2))
    if (e - s + 1) % 3:
        baddiv += 1
    ok += 1
    u5.append(s - 1)
    cl.append(e - s + 1)
    u3.append(length - e)
    if sym == "PDCD4":
        pdcd4 = (ver, length, s, e, syn)


print("records            ", n)
print("  with CDS         ", ok)
print("  without CDS      ", nocds)
print("  bad CDS location ", badloc)
print("seq length mismatch", badlen, " <- must be 0")
print("CDS not div by 3   ", baddiv, " <- must be 0")
print("5'UTR  min/med/max ", min(u5), int(median(u5)), max(u5))
print("CDS    min/med/max ", min(cl), int(median(cl)), max(cl))
print("3'UTR  min/med/max ", min(u3), int(median(u3)), max(u3))
print("no 5'UTR:", sum(1 for x in u5 if x == 0), " no 3'UTR:", sum(1 for x in u3 if x == 0))
if pdcd4:
    v, L, s, e, syn = pdcd4
    print("PDCD4:", v, "length", L, "CDS", s, "..", e)
    print("  5'UTR 1-%d  CDS %d-%d  3'UTR %d-%d" % (s - 1, s, e, e + 1, L))
    print("  synonyms:", syn)
