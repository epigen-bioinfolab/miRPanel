"""Write one target 3'UTR and one miRNA to FASTA for an RNAhybrid trial."""
import os, sqlite3, sys
sys.path.insert(0, "src")
from resolve import resolve_mirna, resolve_gene

con = sqlite3.connect("data/processed/mirna.db")
m = resolve_mirna(con, "hsa-miR-21-5p")
g = resolve_gene(con, "PDCD4")
refseq, seq = con.execute("SELECT refseq, sequence FROM transcripts "
                          "WHERE entrez=? AND mane_status='MANE Select'",
                          (g["entrez"],)).fetchone()
s, e = con.execute("SELECT start_pos, end_pos FROM regions "
                   "WHERE refseq=? AND region='3UTR'", (refseq,)).fetchone()
utr = seq[s - 1:e].replace("T", "U")
mseq = con.execute("SELECT sequence FROM mirnas WHERE accession=?",
                   (m["accession"],)).fetchone()[0]

os.makedirs("data/tmp", exist_ok=True)
open("data/tmp/target.fa", "w").write(">%s_3UTR\n%s\n" % (refseq, utr))
open("data/tmp/query.fa", "w").write(">%s\n%s\n" % (m["name"], mseq))
print("target", refseq, "3UTR", len(utr), "nt   query", m["name"], len(mseq), "nt")
print("3UTR spans", s, "-", e, "in the transcript")
