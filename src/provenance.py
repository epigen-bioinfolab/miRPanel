"""Provenance blocks for exported files.

An exported file leaves this tool. It gets emailed, put in a supervisor's
folder, opened again in eight months by someone who cannot ask what produced
it. So every export carries its own answer: which job, which miRNA, which
tools, which filter, which release of every data source, and when.

The block is written as '#' comment lines above the header row. pandas reads
the file with comment='#', R with comment.char='#'. The data below stays a
plain TSV with exactly one header row, so nothing downstream has to know the
block is there.

The versions are read from data_sources - the same table /about reads - so a
file and the page that produced it can never claim different releases.
"""
import datetime

import config


def _sanitise(v):
    """A newline inside a value would end the comment line, and everything
    after it would look like data. Nothing in a provenance block is worth
    that risk."""
    if v is None:
        return ""
    return str(v).replace("\r", " ").replace("\n", " ")


def _line(key, value):
    """One aligned 'key: value' comment line."""
    return "# %-22s %s" % (key + ":", _sanitise(value))


def _head(kind):
    return ["# %s %s - %s" % (config.TOOL_NAME, config.TOOL_VERSION, kind),
            _line("exported_at",
                  datetime.datetime.now().isoformat(timespec="seconds"))]


def _sources(con):
    """Every data source and its release.

    One line per loaded file, not per project the file came from. The four
    historical miRBase releases are listed because miRNA aliases resolve
    through them: a file claiming only 'miRBase 23' would understate what
    produced it.
    """
    rows = con.execute("SELECT name, version, downloaded_on FROM data_sources "
                       "ORDER BY name").fetchall()
    out = []
    for name, version, downloaded in rows:
        # several loaders name a file after its own release, and printing the
        # version again gives 'miRBase_mature_20 20'
        label = str(name) if version and str(name).endswith(str(version)) \
            else "%s %s" % (name, version)
        out.append(_line("source", "%s (downloaded %s)" % (label,
                                                           downloaded or "?")))
    return out


def results(con, st, filters=None, order=None):
    """The block for a job's result rows. `st` is orchestrator.job_status()."""
    p = st["params"]
    out = _head("results export")
    out += [_line("job_id", st["job_id"]),
            _line("job_status", st["status"]),
            _line("job_finished_at", st["finished_at"]),
            _line("mirna", p["mirna_name"]),
            _line("mirna_accession", p["mirna_acc"]),
            _line("query", p["mirna_query"]),
            _line("query_matched_by", p["matched_by"])]
    # Which transcripts were scanned is not a detail: a 9-gene job and a
    # transcriptome-wide job produce files that look identical otherwise.
    out.append(_line("target_set",
                     "%d requested genes" % len(p["genes"]) if p.get("genes")
                     else "whole transcriptome (every MANE Select transcript)"))
    # Per tool, including the ones that failed. A tool missing from this list
    # was never asked for; a tool listed as 'failed' found nothing because it
    # broke, which is not the same as finding nothing.
    for t in st["tools"]:
        out.append(_line("tool", "%s: %s, %s rows, %ss"
                         % (t["tool"], t["status"], t["n_results"],
                            t["seconds"])))
    applied = {k: v for k, v in (filters or {}).items() if v}
    out.append(_line("filter",
                     ", ".join("%s=%s" % kv for kv in sorted(applied.items()))
                     if applied else "none - every row of this job"))
    if order:
        out.append(_line("sorted_by", order))
    out += _sources(con)
    out += ["# an empty cell is NULL in the database: the tool reported no "
            "value for that field",
            "# scores belong to the tool in the 'tool' column and are on that "
            "tool's own scale - they are not comparable between tools and are "
            "never combined here"]
    return out


def enrichment(con, r, source=None, q=None):
    """The block for an enrichment run. `r` is enrichment.get_run()."""
    out = _head("enrichment export")
    out += [_line("run_id", r["run_id"]),
            _line("job_id", r["job_id"]),
            _line("run_status", r["status"]),
            _line("finished_at", r["finished_at"]),
            # A stale run is still a valid scientific result - it is just a
            # result about a job that no longer exists in that form. Say so
            # rather than hiding it or refusing to export.
            _line("stale", "yes - the job has been re-run since this analysis"
                  if r.get("stale") else "no"),
            _line("gene_selection", r["rule_sentence"]),
            _line("genes_tested", r["n_genes"]),
            _line("genes_annotated", r["n_genes_annotated"]),
            _line("background", "%s (%s %s)"
                  % (r["background"], r["background_source"],
                     r["background_version"])),
            _line("background_size", r["n_background"]),
            _line("ontologies", r["ontologies"]),
            _line("p_adjust_method", r["p_adjust_method"]),
            _line("p_cutoff", r["p_cutoff"]),
            _line("q_cutoff", r["q_cutoff"]),
            _line("r_version", r["r_version"]),
            _line("clusterprofiler", r["clusterprofiler_version"]),
            _line("org_hs_eg_db", r["orgdb_version"]),
            _line("kegg_fetched_at", r["kegg_fetched_at"])]
    if source or q:
        out.append(_line("filter", "source=%s q=%s"
                         % (source or "all sources", q or "")))
    out += _sources(con)
    out += ["# n_in_list and n_in_background are per ontology, not per run: "
            "each ontology annotates a different part of the genome",
            "# every p-value in this file can be recomputed from the four "
            "k/n integers in its own row, without R"]
    return out
