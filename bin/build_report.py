#!/usr/bin/env python3
"""Build the self-contained run report and one report per test sample.

Everything is read from the current directory (Nextflow stages all inputs
flat). Output: wf-gut-report.html and <alias>.sample_report.html.
"""
import argparse
import base64
import csv
import datetime as dt
import glob
import html
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gutlib as g

CSS = """
:root{--bg:#fff;--fg:#1d2733;--mut:#5b6b7b;--card:#f5f7fa;--line:#dde3ea;--ok:#1a7f4b;--warn:#a86400;--bad:#b3261e;--acc:#2a5db0}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--fg:#e6ebf0;--mut:#9aa8b6;--card:#18202a;--line:#2b3744;--ok:#5cc58c;--warn:#e0a24a;--bad:#f07a72;--acc:#7aa7f0}}
body{font:14px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:0 16px 48px}
main{max-width:1100px;margin:0 auto}h1{font-size:22px;margin:24px 0 4px}h2{font-size:17px;margin:32px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.mut{color:var(--mut)}.banner{padding:10px 14px;border-radius:8px;margin:12px 0;border:1px solid var(--line);background:var(--card)}
.PASS,.ok{color:var(--ok);font-weight:600}.WARN,.warn{color:var(--warn);font-weight:600}.FAIL,.bad,.EXPIRED,.MISSING,.ALERT{color:var(--bad);font-weight:600}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:12.5px}th,td{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
th{background:var(--card);position:sticky;top:0}.wrap{overflow-x:auto}img{max-width:100%;height:auto;background:#fff;border-radius:6px}
details{margin:6px 0}summary{cursor:pointer;font-weight:600}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
"""


def esc(x):
    return html.escape(str(x))


def table(rows, cols, cls=None, limit=None):
    if not rows:
        return "<p class='mut'>No data.</p>"
    out = ["<div class='wrap'><table><tr>%s</tr>" % "".join("<th>%s</th>" % esc(c) for c in cols)]
    for r in (rows[:limit] if limit else rows):
        cells = []
        for c in cols:
            v = r.get(c, "")
            if isinstance(v, float):
                v = "%.4g" % v
            k = " class='%s'" % esc(v) if cls and c == cls and str(v) in ("PASS", "WARN", "FAIL", "ALERT") else ""
            cells.append("<td%s>%s</td>" % (k, esc(v)))
        out.append("<tr>%s</tr>" % "".join(cells))
    out.append("</table></div>")
    if limit and len(rows) > limit:
        out.append("<p class='mut'>Showing %d of %d rows; full table in the output folder.</p>" % (limit, len(rows)))
    return "".join(out)


def fig_tag(fig, alt):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return "<img alt='%s' src='data:image/png;base64,%s'>" % (esc(alt), base64.b64encode(buf.getvalue()).decode())


def png_tag(path, alt):
    if not os.path.exists(path):
        return ""
    return "<img alt='%s' src='data:image/png;base64,%s'>" % (esc(alt), base64.b64encode(open(path, "rb").read()).decode())


def load(path):
    return g.read_tsv(path) if os.path.exists(path) else []


def species(alias):
    return [r for r in load("%s.species.tsv" % alias) if str(r.get("kept")) == "True"]


def yield_chart(qc, target):
    names = [r["sample"] for r in qc]
    vals = [g.fnum(r["filtered_gb"]) for r in qc]
    cols = {"PASS": "#4c9a6a", "WARN": "#d69a2d", "FAIL": "#c4453c"}
    fig, ax = plt.subplots(figsize=(max(5, 0.5 * len(names) + 2), 3.4))
    ax.bar(names, vals, color=[cols.get(r["status"], "#888") for r in qc])
    ax.axhline(target, ls="--", lw=1, color="#555")
    ax.text(0, target, " %.1f Gb target" % target, va="bottom", fontsize=7)
    ax.set_ylabel("Gb after filtering")
    plt.setp(ax.get_xticklabels(), rotation=60, ha="right", fontsize=7)
    return fig_tag(fig, "Yield per sample")


def composition_chart(samples, top=12):
    tabs = {s: {r["taxon"]: g.fnum(r["final_rel_abundance"]) for r in species(s)} for s in samples}
    tot = {}
    for t in tabs.values():
        for k, v in t.items():
            tot[k] = tot.get(k, 0) + v
    keep = [k for k, _ in sorted(tot.items(), key=lambda kv: -kv[1])[:top]]
    if not keep:
        return "<p class='mut'>No species calls.</p>"
    cmap = plt.get_cmap("tab20")
    fig, ax = plt.subplots(figsize=(max(5, 0.5 * len(samples) + 3), 4))
    bottom = [0.0] * len(samples)
    for i, k in enumerate(keep):
        v = [tabs[s].get(k, 0.0) for s in samples]
        ax.bar(samples, v, bottom=bottom, color=cmap(i % 20), label=k)
        bottom = [b + x for b, x in zip(bottom, v)]
    other = [max(0.0, 1 - b) for b in bottom]
    ax.bar(samples, other, bottom=bottom, color="#cccccc", label="Other")
    ax.set_ylabel("relative abundance")
    ax.legend(fontsize=6, bbox_to_anchor=(1.01, 1), loc="upper left")
    plt.setp(ax.get_xticklabels(), rotation=60, ha="right", fontsize=7)
    return fig_tag(fig, "Species composition")


def banner_status(ctrl):
    s = ctrl.get("status", "MISSING")
    return "<div class='banner'>Patient result release: <span class='%s'>%s</span> &middot; %s</div>" % (
        esc(s), esc(s), esc(ctrl.get("reason", "")))


def versions_block():
    rows = []
    for p in sorted(glob.glob("*.versions.txt")):
        for line in open(p):
            if line.strip():
                rows.append(line.strip())
    uniq = sorted(set(rows))
    return "<pre class='mut'>%s</pre>" % esc("\n".join(uniq)) if uniq else "<p class='mut'>Not recorded.</p>"


def page(title, body, meta):
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body><main><h1>%s</h1><p class='mut'>%s</p>%s"
            "<p class='mut' style='margin-top:32px'>Wellness/research report. It is not a diagnosis. "
            "Interpret with clinical context.</p></main></body></html>") % (esc(title), CSS, esc(title), esc(meta), body)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", default="dev")
    ap.add_argument("--params_json", default=None)
    ap.add_argument("--target_gb", type=float, default=3.0)
    ap.add_argument("--clinic", default="Panbiome")
    a = ap.parse_args()

    sheet = (list(csv.DictReader(open("sample_sheet.validated.csv")))
             if os.path.exists("sample_sheet.validated.csv") else [])
    qc = load("qc_summary.tsv")
    qcj = json.load(open("qc_summary.json")) if os.path.exists("qc_summary.json") else {}
    ctrl = json.load(open("control_status.json")) if os.path.exists("control_status.json") else {}
    warns = [l.strip() for l in open("sample_sheet.warnings.txt")] if os.path.exists("sample_sheet.warnings.txt") else []
    test = [r["alias"] for r in sheet if r["type"] == "test_sample"]
    meta = "Pipeline %s &middot; generated %s" % (a.version, dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    meta = html.unescape(meta)
    alpha = load("diversity/alpha_diversity.tsv")
    dsum = json.load(open("diversity/diversity_summary.json")) if os.path.exists("diversity/diversity_summary.json") else {}
    flags = load("control_contaminant_flags.tsv")

    def sample_sections(s):
        parts = []
        q = [r for r in qc if r["sample"] == s]
        parts.append("<h2>Run quality</h2>" + table(q, ["sample", "status", "filtered_gb", "filtered_reads", "n50",
                                                         "mean_q", "basecall_tier", "adapter_any_pct", "host_pct", "flags"], cls="status"))
        sp = species(s)
        parts.append("<h2>Species</h2>" + table(
            [{"taxon": r["taxon"], "rel_abundance": g.fnum(r["final_rel_abundance"]), "reads": r["final_reads"],
              "evidence": r["evidence"], "ani": r["sylph_ani"], "lineage": r["lineage"]} for r in sp],
            ["taxon", "rel_abundance", "reads", "evidence", "ani", "lineage"], limit=60))
        wl = [r for r in load("%s.watchlist.tsv" % s)]
        parts.append("<h2>Watchlist</h2>" + table(wl, ["taxon", "rel_abundance", "threshold", "flag", "note"], cls="flag"))
        cf = [r for r in flags if r["sample"] == s]
        if cf:
            parts.append("<h2>Possible reagent contaminants</h2>" + table(cf, ["taxon", "sample_rel_abundance", "blank_rel_abundance", "ratio"]))
        al = [r for r in alpha if r["sample"] == s]
        parts.append("<h2>Alpha diversity</h2>" + table(al, ["sample", "observed_species", "shannon", "simpson", "pielou_evenness"]))
        amr = load("%s.amr_linked.tsv" % s)
        parts.append("<h2>Resistance and virulence genes (genotype only)</h2>" + table(
            amr, ["gene", "class", "type", "contig", "pct_identity", "pct_coverage", "confidence", "on_plasmid",
                  "contig_circular", "bin", "bin_taxon"], limit=100))
        parts.append("<h2>Genomes recovered (MAGs)</h2>" + table(
            load("%s.mags.tsv" % s), ["bin", "n_contigs", "size_bp", "n50", "completeness", "contamination",
                                       "mimag_quality", "taxonomy"]))
        ft = load("%s.function_targets.tsv" % s)
        parts.append("<h2>Targeted gut functions (starter set)</h2>" + table(
            ft, ["function", "gene", "ko", "n_genes", "depth_weighted", "detected"]))
        return "".join(parts)

    # ---------- run report ----------
    body = [banner_status(ctrl)]
    if warns:
        body.append("<div class='banner'><b>Notes</b><br>%s</div>" % "<br>".join(esc(w) for w in warns))
    if qcj.get("run_flags"):
        body.append("<div class='banner warn'>%s</div>" % "<br>".join(esc(x) for x in qcj["run_flags"]))
    body.append("<p>%d samples &middot; %d FAIL &middot; %d WARN &middot; %.1f Gb after filtering &middot; flow cell(s): %s &middot; pores at load: %s &middot; run hours: %s</p>" % (
        qcj.get("samples", 0), qcj.get("n_fail", 0), qcj.get("n_warn", 0), qcj.get("total_filtered_gb", 0.0),
        esc(", ".join(qcj.get("flow_cell_ids", [])) or "n/a"), esc(qcj.get("pore_count_at_load") or "n/a"),
        esc(qcj.get("run_hours") or "n/a")))
    body.append("<h2>Run quality</h2>" + yield_chart(qc, a.target_gb) + table(
        qc, ["sample", "type", "status", "filtered_gb", "filtered_reads", "n50", "mean_q", "basecall_tier",
             "adapter_any_pct", "host_pct", "pgx_carryover_reads", "flags"], cls="status"))
    body.append("<h2>Controls</h2>" + table(
        [{"item": k, "value": v} for k, v in ctrl.items()], ["item", "value"]) + (
        "<h3>Taxa overlapping the control run's contaminant list</h3>" + table(flags, ["sample", "taxon", "sample_rel_abundance", "blank_rel_abundance", "ratio"]) if flags else ""))
    body.append("<h2>Community composition</h2>" + composition_chart(test))
    body.append("<h2>Diversity</h2><div class='grid'>%s%s%s</div>%s" % (
        png_tag("diversity/pcoa_braycurtis.png", "PCoA"), png_tag("diversity/rarefaction.png", "Rarefaction"),
        png_tag("diversity/alpha_shannon.png", "Shannon"),
        table(alpha, ["sample", "observed_species", "shannon", "simpson", "pielou_evenness", "classified_reads"])))
    perm = {k: v for k, v in dsum.items() if k.startswith("permanova")}
    if perm:
        body.append("<p class='mut'>PERMANOVA: %s</p>" % esc(json.dumps(perm)))
    wl_all = []
    for s in test:
        wl_all += [r for r in load("%s.watchlist.tsv" % s) if r["flag"] == "ALERT"]
    body.append("<h2>Watchlist alerts</h2>" + table(wl_all, ["sample", "taxon", "rel_abundance", "threshold", "flag", "note"], cls="flag"))
    amr_all = []
    for s in test:
        amr_all += load("%s.amr_linked.tsv" % s)
    body.append("<h2>Resistance and virulence genes (genotype only)</h2>" + table(
        amr_all, ["sample", "gene", "class", "type", "contig", "pct_identity", "pct_coverage", "confidence",
                  "on_plasmid", "contig_circular", "bin_taxon"], limit=300))
    mags_all = []
    for s in test:
        mags_all += load("%s.mags.tsv" % s)
    body.append("<h2>Genomes recovered (MAGs)</h2>" + table(
        mags_all, ["sample", "bin", "size_bp", "n50", "completeness", "contamination", "mimag_quality", "taxonomy"], limit=300))
    body.append("<h2>Software versions</h2>" + versions_block())
    if a.params_json and os.path.exists(a.params_json):
        body.append("<h2>Parameters</h2><details><summary>Show</summary><pre class='mut'>%s</pre></details>" % esc(open(a.params_json).read()))
    open("wf-gut-report.html", "w").write(page("%s gut microbiome run report" % a.clinic, "".join(body), meta))

    # ---------- per-sample reports ----------
    for s in test:
        b = banner_status(ctrl) + sample_sections(s)
        open("%s.sample_report.html" % s, "w").write(page("%s gut microbiome report: %s" % (a.clinic, s), b, meta))


if __name__ == "__main__":
    main()
