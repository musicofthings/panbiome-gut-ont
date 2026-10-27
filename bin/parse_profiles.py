#!/usr/bin/env python3
"""Convert classifier outputs to one tidy species table.

Subcommands:
  kraken  Kraken2 report + Bracken species output  (+ Krona text input)
  sylph   sylph profile TSV + genome->GTDB lineage map
  emu     Emu rel-abundance TSV (full-length 16S)

Output columns: taxon, lineage, reads, rel_abundance, method, ani, coverage
rel_abundance is a fraction (0-1) among the taxa reported by that method.
"""
import argparse
import re
from collections import defaultdict

import gutlib as g

RANK_LETTER = {"D": "d", "P": "p", "C": "c", "O": "o", "F": "f", "G": "g", "S": "s"}


def parse_kreport(path):
    """Return {taxid: (name, lineage_string)} and krona lines."""
    stack, info, krona = [], {}, []
    with open(path) as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 6:
                continue
            clade, direct, rank, taxid, raw = int(f[1]), int(f[2]), f[3], f[4], f[5]
            depth = (len(raw) - len(raw.lstrip(" "))) // 2
            name = raw.strip()
            stack = stack[:depth] + [(rank, name)]
            parts = [("%s__%s" % (RANK_LETTER[r[0]], n)) for r, n in stack
                     if r and r[0] in RANK_LETTER and len(r) == 1]
            info[taxid] = (name, ";".join(parts))
            if direct > 0:
                krona.append("%d\t%s" % (direct, "\t".join(n for _, n in stack)))
    return info, krona


def cmd_kraken(a):
    info, krona = parse_kreport(a.kreport)
    rows = []
    total_est = 0.0
    br = g.read_tsv(a.bracken)
    for r in br:
        total_est += g.fnum(r.get("new_est_reads"))
    for r in br:
        reads = g.fnum(r.get("new_est_reads"))
        if reads <= 0:
            continue
        tid = r.get("taxonomy_id")
        name = r.get("name", "")
        lineage = info.get(tid, (name, ""))[1]
        rows.append({"taxon": name, "lineage": lineage, "reads": int(round(reads)),
                     "rel_abundance": reads / total_est if total_est else 0.0,
                     "method": "bracken", "ani": "", "coverage": ""})
    rows.sort(key=lambda x: -x["reads"])
    g.write_tsv(rows, a.out, g.SPECIES_COLS)
    if a.krona:
        with open(a.krona, "w") as fh:
            fh.write("\n".join(krona) + ("\n" if krona else ""))


ACC_RE = re.compile(r"(GC[AF]_\d+\.\d+)")


def load_lineage_map(path):
    m = {}
    if not path:
        return m
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            acc = ACC_RE.search(f[0])
            m[acc.group(1) if acc else f[0]] = f[1]
    return m


def cmd_sylph(a):
    lmap = load_lineage_map(a.lineage_map)
    agg = defaultdict(lambda: {"abund": 0.0, "ani": 0.0, "cov": 0.0, "lineage": ""})
    for r in g.read_tsv(a.tsv):
        gf = r.get("Genome_file", "")
        acc = ACC_RE.search(gf)
        key = acc.group(1) if acc else gf.split("/")[-1]
        lineage = lmap.get(key, "")
        taxon = g.species_from_lineage(lineage) or key
        d = agg[taxon]
        d["lineage"] = lineage
        d["abund"] += g.fnum(r.get("Taxonomic_abundance"))
        d["ani"] = max(d["ani"], g.fnum(r.get("Adjusted_ANI")))
        d["cov"] += g.fnum(r.get("Eff_cov"))
    tot = sum(d["abund"] for d in agg.values())
    rows = [{"taxon": t, "lineage": d["lineage"], "reads": "",
             "rel_abundance": d["abund"] / tot if tot else 0.0, "method": "sylph",
             "ani": round(d["ani"], 2), "coverage": round(d["cov"], 4)}
            for t, d in agg.items()]
    rows.sort(key=lambda x: -x["rel_abundance"])
    g.write_tsv(rows, a.out, g.SPECIES_COLS)


def cmd_emu(a):
    rows_in = g.read_tsv(a.tsv)
    tot = sum(g.fnum(r.get("abundance")) for r in rows_in)
    rows = []
    rank_cols = [("superkingdom", "d"), ("phylum", "p"), ("class", "c"),
                 ("order", "o"), ("family", "f"), ("genus", "g"), ("species", "s")]
    for r in rows_in:
        ab = g.fnum(r.get("abundance"))
        sp = r.get("species", "")
        if ab <= 0 or not sp:
            continue
        lineage = ";".join("%s__%s" % (l, r.get(c, "")) for c, l in rank_cols if r.get(c))
        rows.append({"taxon": sp, "lineage": lineage,
                     "reads": int(round(g.fnum(r.get("estimated counts")))) if r.get("estimated counts") else "",
                     "rel_abundance": ab / tot if tot else 0.0, "method": "emu",
                     "ani": "", "coverage": ""})
    rows.sort(key=lambda x: -x["rel_abundance"])
    g.write_tsv(rows, a.out, g.SPECIES_COLS)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kraken")
    k.add_argument("--kreport", required=True)
    k.add_argument("--bracken", required=True)
    k.add_argument("--out", required=True)
    k.add_argument("--krona", default=None)
    k.set_defaults(fn=cmd_kraken)
    s = sub.add_parser("sylph")
    s.add_argument("--tsv", required=True)
    s.add_argument("--lineage_map", default=None)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_sylph)
    e = sub.add_parser("emu")
    e.add_argument("--tsv", required=True)
    e.add_argument("--out", required=True)
    e.set_defaults(fn=cmd_emu)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
