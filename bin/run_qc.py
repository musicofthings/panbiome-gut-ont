#!/usr/bin/env python3
"""Run- and sample-level QC flags.

Combines read stats (raw + filtered), host-split stats and the validated sample
sheet into one table with PASS / WARN / FAIL per sample plus run-level checks
(yield balance across barcodes, flow-cell reuse metadata).
All thresholds are placeholders to be fixed during validation.
"""
import argparse
import csv
import glob
import os
import statistics

import gutlib as g


def load_by_sample(pattern):
    out = {}
    for p in sorted(glob.glob(pattern)):
        d = g.read_json(p)
        out[d["sample"]] = d
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stats_dir", default=".")
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--target_gb", type=float, default=3.0, help="per-sample WARN below")
    ap.add_argument("--min_gb", type=float, default=1.0, help="per-sample FAIL below")
    ap.add_argument("--min_reads", type=int, default=100000)
    ap.add_argument("--min_mean_q", type=float, default=10.0)
    ap.add_argument("--adapter_warn_pct", type=float, default=5.0)
    ap.add_argument("--host_warn_pct", type=float, default=20.0)
    ap.add_argument("--balance_ratio", type=float, default=0.5,
                    help="WARN if yield < ratio * median of test samples")
    ap.add_argument("--pore_count", type=int, default=0, help="available pores at load (metadata)")
    ap.add_argument("--run_hours", type=float, default=0, help="run time in hours (metadata)")
    ap.add_argument("--out_tsv", required=True)
    ap.add_argument("--out_json", required=True)
    a = ap.parse_args()

    raw = load_by_sample(os.path.join(a.stats_dir, "*.raw.stats.json"))
    filt = load_by_sample(os.path.join(a.stats_dir, "*.filtered.stats.json"))
    host = load_by_sample(os.path.join(a.stats_dir, "*.host.json"))
    sheet = list(csv.DictReader(open(a.sheet)))

    test_gb = [filt[r["alias"]]["gb"] for r in sheet
               if r["type"] == "test_sample" and r["alias"] in filt]
    med_gb = statistics.median(test_gb) if test_gb else 0.0

    rows, run_flags = [], []
    for r in sheet:
        s = r["alias"]
        rs, fs, hs = raw.get(s, {}), filt.get(s, {}), host.get(s, {})
        flags, status = [], "PASS"

        def warn(msg):
            nonlocal status
            flags.append(msg)
            if status == "PASS":
                status = "WARN"

        def fail(msg):
            nonlocal status
            flags.append(msg)
            status = "FAIL"

        if not fs:
            fail("no reads after filtering")
        else:
            gb = fs["gb"]
            if fs["reads"] < a.min_reads:
                fail("only %d reads after filtering (min %d)" % (fs["reads"], a.min_reads))
            if r["type"] == "test_sample":
                if gb < a.min_gb:
                    fail("%.2f Gb after filtering is below the %.1f Gb minimum" % (gb, a.min_gb))
                elif gb < a.target_gb:
                    warn("%.2f Gb after filtering is below the %.1f Gb target" % (gb, a.target_gb))
                if med_gb and gb < a.balance_ratio * med_gb:
                    warn("yield is under %.0f%% of the run median (%.2f Gb); check pooling" %
                         (100 * a.balance_ratio, med_gb))
            if rs.get("mean_q", 99) < a.min_mean_q:
                warn("mean read Q %.1f is below %.1f" % (rs["mean_q"], a.min_mean_q))
            tier = rs.get("basecall_tier", "unknown")
            if tier in ("fast", "hac"):
                warn("%s basecalling detected; sup is expected" % tier)
            elif tier == "unknown":
                warn("basecall model could not be read from the headers")
            if rs.get("adapter_any_pct", 0) > a.adapter_warn_pct:
                warn("%.1f%% of reads still carry adapter; enable trimming in MinKNOW/Dorado" %
                     rs["adapter_any_pct"])
        if hs:
            if 100 * hs.get("host_fraction", 0) > a.host_warn_pct:
                warn("high human read fraction (%.1f%%)" % (100 * hs["host_fraction"]))
            if hs.get("pgx_carryover_flag"):
                warn("%d human reads fall in PGx target regions: likely carryover from the "
                     "previous library" % hs["pgx_carryover_reads"])
        rows.append({
            "sample": s, "barcode": r["barcode"], "type": r["type"], "status": status,
            "raw_reads": rs.get("reads", 0), "filtered_reads": fs.get("reads", 0),
            "filtered_gb": round(fs.get("gb", 0.0), 3),
            "n50": fs.get("n50", 0), "mean_q": round(rs.get("mean_q", 0.0), 2),
            "median_read_q": round(rs.get("median_read_q", 0.0), 2),
            "basecall_tier": rs.get("basecall_tier", ""), "basecall_model": rs.get("basecall_model", ""),
            "adapter_any_pct": round(rs.get("adapter_any_pct", 0.0), 2),
            "host_pct": round(100 * hs.get("host_fraction", 0.0), 2),
            "nonhost_reads": hs.get("nonhost_reads", 0),
            "pgx_carryover_reads": hs.get("pgx_carryover_reads", 0),
            "flags": "; ".join(flags),
        })

    flowcells = sorted({c for d in raw.values() for c in d.get("flow_cell_ids", [])})
    runids = sorted({c for d in raw.values() for c in d.get("run_ids", [])})
    total_gb = sum(x["filtered_gb"] for x in rows)
    if a.pore_count and a.pore_count < 3000:
        run_flags.append("Low available pore count at load (%d)" % a.pore_count)
    cols = ["sample", "barcode", "type", "status", "raw_reads", "filtered_reads",
            "filtered_gb", "n50", "mean_q", "median_read_q", "basecall_tier",
            "basecall_model", "adapter_any_pct", "host_pct", "nonhost_reads",
            "pgx_carryover_reads", "flags"]
    g.write_tsv(rows, a.out_tsv, cols)
    g.write_json({
        "samples": len(rows), "total_filtered_gb": total_gb,
        "median_test_sample_gb": med_gb,
        "n_fail": sum(1 for x in rows if x["status"] == "FAIL"),
        "n_warn": sum(1 for x in rows if x["status"] == "WARN"),
        "flow_cell_ids": flowcells, "run_ids": runids,
        "pore_count_at_load": a.pore_count, "run_hours": a.run_hours,
        "run_flags": run_flags,
    }, a.out_json)


if __name__ == "__main__":
    main()
