"""Does RNAhybrid's length loss grow with size, and does line wrapping fix it?"""
import subprocess

s = open("data/tmp/target.fa").read().split("\n", 1)[1].replace("\n", "")
long_seq = (s * 6)[:10000]

def run(seq, wrap):
    body = seq if wrap == 0 else "\n".join(seq[i:i + wrap] for i in range(0, len(seq), wrap))
    open("data/tmp/len.fa", "w").write(">t\n" + body + "\n")
    out = subprocess.run(
        ["RNAhybrid", "-t", "data/tmp/len.fa", "-q", "data/tmp/query.fa",
         "-s", "3utr_human", "-b", "1", "-f", "2,7"],
        capture_output=True, text=True).stdout
    rep = [l for l in out.split("\n") if l.startswith("length:")]
    return rep[0] if rep else "no output"

for n in (2000, 3000, 5000, 10000):
    print("unwrapped %6d -> %s" % (n, run(long_seq[:n], 0)))
print()
for n in (1000, 2000, 10000):
    print("wrapped60 %6d -> %s" % (n, run(long_seq[:n], 60)))
