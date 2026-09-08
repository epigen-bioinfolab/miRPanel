"""Find where RNAhybrid's reported target length stops matching the input."""
import subprocess

s = open("data/tmp/target.fa").read().split("\n", 1)[1].replace("\n", "")
for n in (500, 1000, 1500, 1700, 1800, 1900, 1910, 1915, 1917, 1918):
    open("data/tmp/len.fa", "w").write(">t\n" + s[:n] + "\n")
    out = subprocess.run(
        ["RNAhybrid", "-t", "data/tmp/len.fa", "-q", "data/tmp/query.fa",
         "-s", "3utr_human", "-b", "1", "-f", "2,7"],
        capture_output=True, text=True).stdout
    rep = [l for l in out.split("\n") if l.startswith("length:")]
    print("input %5d  ->  %s" % (n, rep[0] if rep else "no output"))
