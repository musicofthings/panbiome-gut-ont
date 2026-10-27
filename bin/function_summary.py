#!/usr/bin/env python3
"""Summarize eggNOG-mapper annotations of predicted genes.

Abundance proxy: mean read depth of the contig carrying each gene (from the
Flye assembly_info cov. column). This is approximate and favors abundant
organisms; it is NOT a per-gene read count.

Outputs: KO table, KEGG module table, CAZy family table, and a targeted table
for a starter set of gut functions (see assets/functional_targets.tsv).
"""
import argparse
import os
from collections import defaultdict

import gutlib as g


def depth_map(path):
    d = {}
    if path and os.path.exists(path):
        for r in g.read_tsv(path):
            d[r.get("#seq_name") or r.get("seq_name")] = g.fnum(r.get("cov."), 1.0)
    return d


def split_ids(v):
    return [x for x in (v or "").split(",") if x and x != "-"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--assembly_info", default=None)
    ap.add_argument("--targets", default=None)
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()

    depth = depth_map(a.assembly_info)
    ko, mod, caz = defaultdict(lambda: [0, 0.0]), defaultdict(lambda: [0, 0.0]), defaultdict(lambda: [0, 0.0])
    lines = [l for l in open(a.annotations) if not l.startswith("##") and l.strip()]
    if lines:
        hdr = lines[0].lstrip("#").rstrip("\n").split("\t")
        for line in lines[1:]:
            f = line.rstrip("\n").split("\t")
            if len(f) < len(hdr):
                continue
            r = dict(zip(hdr, f))
            contig = r["query"].rsplit("_", 1)[0]
            d = depth.get(contig, 1.0)
            for k in split_ids(r.get("KEGG_ko")):
                k = k.replace("ko:", "")
                ko[k][0] += 1
                ko[k][1] += d
            for m in split_ids(r.get("KEGG_Module")):
                mod[m][0] += 1
                mod[m][1] += d
            for c in split_ids(r.get("CAZy")):
                caz[c][0] += 1
                caz[c][1] += d

    def dump(tab, name, idcol):
        rows = [{"sample": a.sample, idcol: k, "n_genes": v[0], "depth_weighted": round(v[1], 3)}
                for k, v in sorted(tab.items(), key=lambda kv: -kv[1][1])]
        g.write_tsv(rows, os.path.join(a.outdir, "%s.%s.tsv" % (a.sample, name)),
                    ["sample", idcol, "n_genes", "depth_weighted"])
    dump(ko, "function_ko", "ko")
    dump(mod, "function_module", "module")
    dump(caz, "function_cazy", "cazy_family")

    trows = []
    if a.targets and os.path.exists(a.targets):
        for t in g.read_tsv(a.targets):
            hit = ko.get(t["ko"], [0, 0.0])
            trows.append({"sample": a.sample, "function": t["function"], "gene": t["gene"],
                          "ko": t["ko"], "n_genes": hit[0], "depth_weighted": round(hit[1], 3),
                          "detected": hit[0] > 0})
    g.write_tsv(trows, os.path.join(a.outdir, "%s.function_targets.tsv" % a.sample),
                ["sample", "function", "gene", "ko", "n_genes", "depth_weighted", "detected"])


if __name__ == "__main__":
    main()
