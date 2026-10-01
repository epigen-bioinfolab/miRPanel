"""HEAD every download URL the organism picker offers.

    python3 scripts/check_species_urls.py

Run this after changing src/species.py, and again before any release.

WHY THIS IS A PERMANENT SCRIPT AND NOT A ONE-OFF
------------------------------------------------
These URLs are built from strings in species.py, and Ensembl changes
both halves underneath them:

  - assemblies are replaced. Rat moved from mRatBN7.2 to GRCr8, and the
    old filename simply 404s.
  - release numbering is not uniform. Drosophila is annotated by Ensembl
    Genomes, which counts separately - its GTF carries 63 where the
    vertebrates carry 116. The fly cDNA FASTA has no release number in
    its name, so it kept working while its GTF did not.

Neither failure shows up anywhere in the tool. The links render fine,
the page looks correct, and the first person to find out is a user who
clicks one. That is the wrong person to find out.

Exit status is 1 if anything is unreachable, so this can gate a release.
"""
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import species as sp                                       # noqa: E402

TIMEOUT = 25


def head(url):
    """(status, note). A HEAD, so nothing is downloaded."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            size = r.headers.get("Content-Length")
            mb = ("%.0f MB" % (int(size) / 1e6)) if size else ""
            return r.status, mb
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:                                 # network, DNS, TLS
        return None, str(e)[:60]


def main():
    bad = 0
    for key in sp.SPECIES:
        if key in sp.PRELOADED:
            print("%-8s preloaded, no download offered" % key)
            continue
        for kind, url in (("fasta", sp.fasta_url(key)),
                          ("gtf", sp.gtf_url(key))):
            status, note = head(url)
            ok = status == 200
            bad += not ok
            print("%-8s %-5s %-4s %-9s %s" % (
                key, kind, status if status else "ERR", note,
                url.rsplit("/", 1)[1]))
            if not ok:
                print("         ^ unreachable: check the assembly string and "
                      "release number for %s in src/species.py" % key)
    if bad:
        print("\n%d unreachable URL(s). The picker would offer links that "
              "404." % bad)
    else:
        print("\nall download URLs resolve.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
