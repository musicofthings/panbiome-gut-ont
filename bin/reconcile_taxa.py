#!/usr/bin/env python3
"""Reconcile species calls from independent methods into one table.

Evidence per species:
  bracken  detected when estimated reads >= --min_reads
  sylph    detected when adjusted ANI >= --min_ani and coverage >= --min_cov
  emu      (16S track) detected when relative abundance >= --min_rel
Rule 'both' (default when two shotgun methods are present) keeps a species only
if every available shotgun method supports it; rule 'either' keeps the union.
Final abundance comes from --primary (bracken | sylph | emu) and is renormalized
over the kept species. Both shotgun databases MUST use the same taxonomy
(GTDB recommended); a synonyms file can map residual name differences.

Also evaluates the gut watchlist (taxon, min_rel_abundance, note).
"""
import argparse

import gutlib as g

OUT_COLS = ["taxon", "lineage", "evidence", "n_methods", "bracken_reads",
            "bracken_rel", "sylph_rel", "sylph_ani", "sylph_cov", "emu_rel",
            "kept", "final_reads", "final_rel_abundance"]


def load(path):
    if not path:
        return {}
    return {r["taxon"]: r for r in g.read_tsv(path)}


def load_synonyms(path):
    syn = {}
    if path:
        for line in open(path):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2 and not line.startswith("#"):
                syn[g.norm_taxon(f[0])] = f[1]
    return syn


def apply_syn(tab, syn):
    if not syn:
        return tab
    out = {}
    for t, r in tab.items():
        out[syn.get(g.norm_taxon(t), t)] = r
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--bracken", default=None)
    ap.add_argument("--sylph", default=None)
    ap.add_argument("--emu", default=None)
    ap.add_argument("--synonyms", default=None)
    ap.add_argument("--watchlist", default=None)
    ap.add_argument("--rule", choices=["both", "either"], default="both")
    ap.add_argument("--primary", choices=["bracken", "sylph", "emu"], default="bracken")
    ap.add_argument("--min_reads", type=float, default=50)
    ap.add_argument("--min_ani", type=float, default=95.0)
    ap.add_argument("--min_cov", type=float, default=0.0)
    ap.add_argument("--min_rel", type=float, default=0.0001)
    ap.add_argument("--out", required=True)
    ap.add_argument("--watch_out", required=True)
    ap.add_argument("--json", required=True)
    a = ap.parse_args()

    syn = load_synonyms(a.synonyms)
    br, sy, em = (apply_syn(load(a.bracken), syn), apply_syn(load(a.sylph), syn),
                  apply_syn(load(a.emu), syn))
    methods = [m for m, t in (("bracken", br), ("sylph", sy), ("emu", em)) if t]
    if a.primary not in methods and methods:
        a.primary = methods[0]

    rows = []
    for t in sorted(set(br) | set(sy) | set(em)):
        b, s, e = br.get(t), sy.get(t), em.get(t)
        ev = []
        if b and g.fnum(b.get("reads")) >= a.min_reads:
            ev.append("bracken")
        if s and g.fnum(s.get("ani")) >= a.min_ani and g.fnum(s.get("coverage")) >= a.min_cov:
            ev.append("sylph")
        if e and g.fnum(e.get("rel_abundance")) >= a.min_rel:
            ev.append("emu")
        shotgun_methods = [m for m in methods if m in ("bracken", "sylph")]
        if a.rule == "both" and len(shotgun_methods) == 2:
            kept = all(m in ev for m in shotgun_methods)
        else:
            kept = bool(ev)
        lineage = next((x["lineage"] for x in (b, s, e) if x and x.get("lineage")), "")
        rows.append({
            "taxon": t, "lineage": lineage, "evidence": "+".join(ev) or "below_threshold",
            "n_methods": len(ev),
            "bracken_reads": b["reads"] if b else "",
            "bracken_rel": b["rel_abundance"] if b else "",
            "sylph_rel": s["rel_abundance"] if s else "",
            "sylph_ani": s["ani"] if s else "",
            "sylph_cov": s["coverage"] if s else "",
            "emu_rel": e["rel_abundance"] if e else "",
            "kept": kept,
        })

    prim_col = {"bracken": "bracken_rel", "sylph": "sylph_rel", "emu": "emu_rel"}.get(a.primary)
    tot = sum(g.fnum(r[prim_col]) for r in rows if r["kept"]) if prim_col else 0.0
    for r in rows:
        v = g.fnum(r[prim_col]) if (prim_col and r["kept"]) else 0.0
        r["final_rel_abundance"] = v / tot if tot else 0.0
        r["final_reads"] = (int(g.fnum(r["bracken_reads"])) if (a.primary == "bracken" and r["kept"] and r["bracken_reads"] != "")
                            else int(round(r["final_rel_abundance"] * 1e6)))
    rows.sort(key=lambda x: -x["final_rel_abundance"])
    g.write_tsv(rows, a.out, OUT_COLS)

    kept_rows = [r for r in rows if r["kept"]]
    watch_rows = []
    if a.watchlist:
        for w in g.read_tsv(a.watchlist):
            wt = g.norm_taxon(w["taxon"])
            thr = g.fnum(w.get("min_rel_abundance"), 0.01)
            hits = [r for r in kept_rows if g.norm_taxon(r["taxon"]) == wt
                    or g.norm_taxon(r["taxon"]).startswith(wt + " ")]
            ab = sum(r["final_rel_abundance"] for r in hits)
            watch_rows.append({"sample": a.sample, "taxon": w["taxon"],
                               "rel_abundance": ab, "threshold": thr,
                               "flag": "ALERT" if ab >= thr and hits else "none",
                               "note": w.get("note", "")})
    g.write_tsv(watch_rows, a.watch_out,
                ["sample", "taxon", "rel_abundance", "threshold", "flag", "note"])

    g.write_json({
        "sample": a.sample, "methods": methods, "primary": a.primary, "rule": a.rule,
        "species_kept": len(kept_rows), "species_total_candidates": len(rows),
        "both_methods_agree": sum(1 for r in kept_rows if r["n_methods"] >= 2),
        "watchlist_alerts": [w["taxon"] for w in watch_rows if w["flag"] == "ALERT"],
    }, a.json)


if __name__ == "__main__":
    main()
