#!/usr/bin/env python3
"""Link AMR / virulence genes to contig, MAG, taxon and plasmid context.

Inputs are all optional except --amr. Long reads let a gene be tied to the
contig it sits on, whether that contig is circular, whether geNomad calls it a
plasmid, and which MAG (and taxon) it belongs to.

Confidence tiers follow the BugSeq convention for gene-based calls:
  very_high  100% identity and 100% coverage
  high       100% identity, <100% coverage
  moderate   below that
Only genes passing --min_cov / --min_id are reported ("complete genes").
This is GENOTYPE reporting only. No phenotype is predicted for mixed samples.
"""
import argparse
import csv
import os
import re

import gutlib as g

OUT = ["sample", "gene", "name", "type", "subtype", "class", "subclass", "contig",
       "start", "stop", "pct_identity", "pct_coverage", "confidence", "method",
       "contig_len", "contig_circular", "contig_depth", "plasmid_score", "on_plasmid",
       "bin", "bin_taxon", "bin_quality"]


def col(row, *needles):
    for k in row:
        kl = k.lower()
        if all(n in kl for n in needles):
            return row[k]
    return ""


def read_assembly_info(path):
    d = {}
    if not path or not os.path.exists(path):
        return d
    for r in g.read_tsv(path):
        d[r["#seq_name"] if "#seq_name" in r else r.get("seq_name")] = {
            "len": g.fnum(r.get("length")), "cov": g.fnum(r.get("cov.")),
            "circ": r.get("circ.", "N") == "Y"}
    return d


def read_plasmid(path):
    d = {}
    if path and os.path.exists(path):
        for r in g.read_tsv(path):
            d[r["seq_name"]] = g.fnum(r.get("plasmid_score"))
    return d


def read_contig_bins(path):
    d = {}
    if path and os.path.exists(path):
        with open(path) as fh:
            rd = csv.reader(fh, delimiter="\t")
            hdr = next(rd, None)
            for row in rd:
                if len(row) >= 2:
                    d[row[0]] = row[1]
    return d


def fasta_stats(path):
    lens, cur = [], 0
    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                if cur:
                    lens.append(cur)
                cur = 0
            else:
                cur += len(line.strip())
    if cur:
        lens.append(cur)
    return lens


def mimag(comp, cont):
    if comp >= 90 and cont < 5:
        return "high"
    if comp >= 50 and cont < 10:
        return "medium"
    return "low"


def mag_table(sample, bins_dir, checkm, gtdb, contig_bins):
    rows = []
    q = {}
    if checkm and os.path.exists(checkm):
        for r in g.read_tsv(checkm):
            q[r["Name"]] = (g.fnum(r.get("Completeness")), g.fnum(r.get("Contamination")))
    tax = {}
    for p in gtdb:
        if os.path.exists(p):
            for r in g.read_tsv(p):
                tax[r["user_genome"]] = r.get("classification", "")
    names = set(contig_bins.values())
    if bins_dir and os.path.isdir(bins_dir):
        for fn in sorted(os.listdir(bins_dir)):
            if re.search(r"\.(fa|fasta|fna)(\.gz)?$", fn):
                names.add(re.sub(r"\.(fa|fasta|fna)(\.gz)?$", "", fn))
    for b in sorted(names):
        lens, p = [], None
        if bins_dir:
            for ext in (".fa", ".fasta", ".fna"):
                cand = os.path.join(bins_dir, b + ext)
                if os.path.exists(cand):
                    p = cand
                    break
        if p:
            lens = fasta_stats(p)
        comp, cont = q.get(b, (None, None))
        rows.append({
            "sample": sample, "bin": b, "n_contigs": len(lens), "size_bp": sum(lens),
            "n50": g.n50(lens), "completeness": "" if comp is None else comp,
            "contamination": "" if cont is None else cont,
            "mimag_quality": mimag(comp, cont) if comp is not None else "unscored",
            "taxonomy": tax.get(b, "")})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--amr", required=True)
    ap.add_argument("--assembly_info", default=None)
    ap.add_argument("--plasmid_summary", default=None)
    ap.add_argument("--contig_bins", default=None)
    ap.add_argument("--bins_dir", default=None)
    ap.add_argument("--checkm", default=None)
    ap.add_argument("--gtdbtk", nargs="*", default=[])
    ap.add_argument("--min_cov", type=float, default=90.0)
    ap.add_argument("--min_id", type=float, default=90.0)
    ap.add_argument("--plasmid_min_score", type=float, default=0.7)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out_mags", required=True)
    a = ap.parse_args()

    asm = read_assembly_info(a.assembly_info)
    pl = read_plasmid(a.plasmid_summary)
    cb = read_contig_bins(a.contig_bins)
    mags = mag_table(a.sample, a.bins_dir, a.checkm, a.gtdbtk, cb)
    mag_by = {m["bin"]: m for m in mags}

    out = []
    if os.path.exists(a.amr) and os.path.getsize(a.amr) > 0:
        for r in g.read_tsv(a.amr):
            cov = g.fnum(col(r, "coverage of reference"))
            idn = g.fnum(col(r, "identity to reference"))
            if cov < a.min_cov or idn < a.min_id:
                continue
            contig = col(r, "contig id")
            if idn >= 100 and cov >= 100:
                conf = "very_high"
            elif idn >= 100:
                conf = "high"
            else:
                conf = "moderate"
            b = cb.get(contig, "")
            score = pl.get(contig)
            out.append({
                "sample": a.sample, "gene": col(r, "element symbol"),
                "name": col(r, "element name"), "type": col(r, "type"),
                "subtype": col(r, "subtype"), "class": col(r, "class"),
                "subclass": col(r, "subclass"), "contig": contig,
                "start": col(r, "start"), "stop": col(r, "stop"),
                "pct_identity": idn, "pct_coverage": cov, "confidence": conf,
                "method": col(r, "method"),
                "contig_len": asm.get(contig, {}).get("len", ""),
                "contig_circular": asm.get(contig, {}).get("circ", ""),
                "contig_depth": asm.get(contig, {}).get("cov", ""),
                "plasmid_score": "" if score is None else score,
                "on_plasmid": bool(score is not None and score >= a.plasmid_min_score),
                "bin": b, "bin_taxon": mag_by.get(b, {}).get("taxonomy", ""),
                "bin_quality": mag_by.get(b, {}).get("mimag_quality", "")})
    g.write_tsv(out, a.out, OUT)
    g.write_tsv(mags, a.out_mags, ["sample", "bin", "n_contigs", "size_bp", "n50",
                                   "completeness", "contamination", "mimag_quality", "taxonomy"])


if __name__ == "__main__":
    main()
