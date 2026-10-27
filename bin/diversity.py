#!/usr/bin/env python3
"""Community tables and diversity for test samples.

Writes: abundance matrices, BIOM (v1.0 JSON), alpha diversity, beta distance
matrices (Bray-Curtis, Jaccard, Aitchison), PCoA, PERMANOVA (if a group
column exists), rarefaction (when integer read counts exist), and PNG plots.
"""
import argparse
import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.distance import pdist, squareform

import gutlib as g


def load_samples(sheet, species_dir):
    samples, tables, meta = [], {}, {}
    for r in sheet:
        if r["type"] != "test_sample":
            continue
        p = os.path.join(species_dir, "%s.species.tsv" % r["alias"])
        if not os.path.exists(p):
            continue
        rows = [x for x in g.read_tsv(p) if str(x.get("kept")) == "True"]
        samples.append(r["alias"])
        tables[r["alias"]] = rows
        meta[r["alias"]] = r
    return samples, tables, meta


def build_matrix(samples, tables):
    taxa = sorted({x["taxon"] for s in samples for x in tables[s]})
    idx = {t: i for i, t in enumerate(taxa)}
    rel = np.zeros((len(taxa), len(samples)))
    cnt = np.zeros_like(rel)
    for j, s in enumerate(samples):
        for x in tables[s]:
            rel[idx[x["taxon"]], j] = g.fnum(x["final_rel_abundance"])
            cnt[idx[x["taxon"]], j] = g.fnum(x["final_reads"])
    return taxa, rel, cnt


def alpha(rel, cnt, samples):
    out = []
    for j, s in enumerate(samples):
        p = rel[:, j]
        p = p[p > 0]
        obs = int((rel[:, j] > 0).sum())
        sh = float(-(p * np.log(p)).sum()) if p.size else 0.0
        out.append({"sample": s, "observed_species": obs,
                    "shannon": round(sh, 4),
                    "simpson": round(float(1 - (p ** 2).sum()) if p.size else 0.0, 4),
                    "pielou_evenness": round(sh / np.log(obs), 4) if obs > 1 else 0.0,
                    "classified_reads": int(cnt[:, j].sum())})
    return out


def clr(rel):
    x = rel.copy()
    nz = x[x > 0]
    pc = (nz.min() / 2) if nz.size else 1e-6
    x = x + pc
    x = x / x.sum(axis=0, keepdims=True)
    lx = np.log(x)
    return lx - lx.mean(axis=0, keepdims=True)


def distances(rel):
    X = rel.T
    out = {"braycurtis": squareform(pdist(X, "braycurtis")),
           "jaccard": squareform(pdist((X > 0).astype(bool), "jaccard")),
           "aitchison": squareform(pdist(clr(rel).T, "euclidean"))}
    return {k: np.nan_to_num(v) for k, v in out.items()}


def pcoa(D, k=3):
    n = D.shape[0]
    if n < 3:
        return None, None
    A = -0.5 * D ** 2
    H = np.eye(n) - np.ones((n, n)) / n
    B = H @ A @ H
    w, v = np.linalg.eigh(B)
    order = np.argsort(w)[::-1]
    w, v = w[order], v[:, order]
    pos = w > 1e-12
    coords = v[:, pos] * np.sqrt(w[pos])
    expl = w[pos] / w[pos].sum() if pos.any() else np.array([])
    kk = min(k, coords.shape[1])
    return coords[:, :kk], expl[:kk]


def permanova(D, groups, perms=999, seed=1):
    labels = sorted(set(groups))
    n, a_ = len(groups), len(labels)
    if a_ < 2 or n - a_ < 1:
        return None

    def f_stat(gr):
        sst = (D ** 2).sum() / (2 * n)
        ssw = 0.0
        for l in labels:
            idx = [i for i, x in enumerate(gr) if x == l]
            if len(idx) > 1:
                sub = D[np.ix_(idx, idx)]
                ssw += (sub ** 2).sum() / (2 * len(idx))
        ssa = sst - ssw
        return (ssa / (a_ - 1)) / (ssw / (n - a_)) if ssw > 0 else np.inf

    f0 = f_stat(groups)
    rng = np.random.default_rng(seed)
    ge = 1
    for _ in range(perms):
        if f_stat(list(rng.permutation(groups))) >= f0:
            ge += 1
    return {"pseudo_F": float(f0), "p_value": ge / (perms + 1), "permutations": perms,
            "n": n, "groups": a_}


def rarefaction(cnt, samples, steps=10, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for j, s in enumerate(samples):
        c = np.round(cnt[:, j]).astype(np.int64)
        tot = int(c.sum())
        if tot < 100:
            continue
        for d in np.linspace(tot // steps, tot, steps).astype(int):
            sub = rng.multivariate_hypergeometric(c, int(d)) if d < tot else c
            rows.append({"sample": s, "depth": int(d), "observed_species": int((sub > 0).sum())})
    return rows


def write_biom(path, taxa, samples, cnt, rel, meta):
    data = []
    for i in range(len(taxa)):
        for j in range(len(samples)):
            v = cnt[i, j] if cnt[i, j] > 0 else rel[i, j]
            if v > 0:
                data.append([i, j, float(v)])
    doc = {"id": "panbiome-gut-ont", "format": "Biological Observation Matrix 1.0.0",
           "format_url": "http://biom-format.org", "type": "OTU table",
           "generated_by": "panbiome-gut-ont", "matrix_type": "sparse",
           "matrix_element_type": "float", "shape": [len(taxa), len(samples)],
           "data": data,
           "rows": [{"id": t, "metadata": None} for t in taxa],
           "columns": [{"id": s, "metadata": {k: v for k, v in meta[s].items()}} for s in samples]}
    with open(path, "w") as fh:
        json.dump(doc, fh)


def save_matrix(path, rowlabels, collabels, M, corner="taxon"):
    with open(path, "w") as fh:
        fh.write("\t".join([corner] + list(collabels)) + "\n")
        for i, r in enumerate(rowlabels):
            fh.write("\t".join([r] + ["%.6g" % M[i, j] for j in range(M.shape[1])]) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--species_dir", default=".")
    ap.add_argument("--group_col", default="group")
    ap.add_argument("--outdir", default="diversity")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    sheet = list(csv.DictReader(open(a.sheet)))
    samples, tables, meta = load_samples(sheet, a.species_dir)
    summary = {"n_samples": len(samples)}
    if not samples:
        g.write_json(summary, os.path.join(a.outdir, "diversity_summary.json"))
        return
    taxa, rel, cnt = build_matrix(samples, tables)
    if not taxa:
        g.write_json(summary, os.path.join(a.outdir, "diversity_summary.json"))
        return

    save_matrix(os.path.join(a.outdir, "abundance_relative.tsv"), taxa, samples, rel)
    save_matrix(os.path.join(a.outdir, "abundance_counts.tsv"), taxa, samples, cnt)
    write_biom(os.path.join(a.outdir, "feature_table.biom.json"), taxa, samples, cnt, rel, meta)

    al = alpha(rel, cnt, samples)
    g.write_tsv(al, os.path.join(a.outdir, "alpha_diversity.tsv"),
                ["sample", "observed_species", "shannon", "simpson", "pielou_evenness",
                 "classified_reads"])

    if len(samples) >= 2:
        D = distances(rel)
        for k, M in D.items():
            save_matrix(os.path.join(a.outdir, "beta_%s.tsv" % k), samples, samples, M, "sample")
        coords, expl = pcoa(D["braycurtis"])
        if coords is not None:
            with open(os.path.join(a.outdir, "pcoa_braycurtis.tsv"), "w") as fh:
                fh.write("sample\t" + "\t".join("PC%d" % (i + 1) for i in range(coords.shape[1])) + "\n")
                for i, s in enumerate(samples):
                    fh.write(s + "\t" + "\t".join("%.6g" % v for v in coords[i]) + "\n")
            summary["pcoa_explained"] = [float(x) for x in expl]
            groups = [meta[s].get(a.group_col, "") for s in samples]
            fig, ax = plt.subplots(figsize=(5, 4.2))
            uniq = sorted(set(groups))
            cmap = plt.get_cmap("tab10")
            for gi, gname in enumerate(uniq):
                ids = [i for i, x in enumerate(groups) if x == gname]
                ax.scatter(coords[ids, 0], coords[ids, 1] if coords.shape[1] > 1 else 0,
                           s=48, color=cmap(gi % 10), label=gname or "samples")
            for i, s in enumerate(samples):
                ax.annotate(s, (coords[i, 0], coords[i, 1] if coords.shape[1] > 1 else 0), fontsize=6)
            ax.set_xlabel("PC1 (%.0f%%)" % (100 * expl[0]))
            if coords.shape[1] > 1:
                ax.set_ylabel("PC2 (%.0f%%)" % (100 * expl[1]))
            ax.set_title("PCoA, Bray-Curtis")
            if len(uniq) > 1 or uniq[0]:
                ax.legend(fontsize=7)
            fig.tight_layout()
            fig.savefig(os.path.join(a.outdir, "pcoa_braycurtis.png"), dpi=150)
            plt.close(fig)
        groups = [meta[s].get(a.group_col, "") for s in samples]
        if any(groups) and len(set(groups)) > 1:
            for k in ("braycurtis", "aitchison"):
                res = permanova(D[k], groups)
                if res:
                    summary["permanova_%s" % k] = res

    rar = rarefaction(cnt, samples)
    if rar:
        g.write_tsv(rar, os.path.join(a.outdir, "rarefaction.tsv"),
                    ["sample", "depth", "observed_species"])
        fig, ax = plt.subplots(figsize=(5.5, 4))
        for s in samples:
            pts = [(r["depth"], r["observed_species"]) for r in rar if r["sample"] == s]
            if pts:
                ax.plot(*zip(*pts), marker="o", ms=2, lw=1)
        ax.set_xlabel("classified reads sampled")
        ax.set_ylabel("species observed")
        ax.set_title("Rarefaction (curves flattening = depth is sufficient)")
        fig.tight_layout()
        fig.savefig(os.path.join(a.outdir, "rarefaction.png"), dpi=150)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(max(4, 0.45 * len(samples) + 2), 3.6))
    ax.bar(samples, [r["shannon"] for r in al], color="#4c78a8")
    ax.set_ylabel("Shannon index")
    ax.set_title("Alpha diversity")
    plt.setp(ax.get_xticklabels(), rotation=60, ha="right", fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(a.outdir, "alpha_shannon.png"), dpi=150)
    plt.close(fig)

    g.write_json(summary, os.path.join(a.outdir, "diversity_summary.json"))


if __name__ == "__main__":
    main()
