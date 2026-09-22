"""Record scanMiR's model data in data_sources.

scanMiR is not a downloaded file like MANE or TargetScan - it arrives as an R
package - but its KdModels are a versioned data source, and every export
promises to list every source that produced it. Without this row /about, the
provenance block and all three export formats would quietly omit the tool
that produced the ML column.

There is no file to hash, so bytes and sha256 are NULL. The version is read
from the installed package rather than typed here, so the row cannot drift
from what actually ran.

Rerunnable: INSERT OR REPLACE, so running it after an upgrade updates the row.
"""
import datetime, subprocess, sys

sys.path.insert(0, "src")
import db

R = """
suppressPackageStartupMessages({library(scanMiR); library(scanMiRData)})
cat(as.character(packageVersion("scanMiR")), "\n", sep="")
cat(as.character(packageVersion("scanMiRData")), "\n", sep="")
cat(length(getKdModels("hsa")), "\n", sep="")
"""

p = subprocess.run(["Rscript", "-e", R], capture_output=True, text=True)
if p.returncode != 0:
    sys.exit("could not query the R packages: %s" % p.stderr.strip()[:300])
scanmir_v, data_v, n_models = [l.strip() for l in p.stdout.strip().splitlines()[:3]]

con = db.connect()
con.execute(
    "INSERT OR REPLACE INTO data_sources VALUES (?,?,?,?,?,?,?)",
    ("scanMiRData", data_v, "bioconductor.org/packages/scanMiRData",
     datetime.date.today().isoformat(), None, None,
     "%s human KdModels, CNN affinity model (McGeary et al. Science 2019); "
     "scanned by scanMiR %s; models built on miRBase 22, so 243 miRNAs whose "
     "seed was revised in Release 23 have no usable model"
     % (n_models, scanmir_v)))
con.commit()

for row in con.execute("SELECT name, version, downloaded_on, notes "
                       "FROM data_sources WHERE name='scanMiRData'"):
    print(row)
