#!/usr/bin/env python3
"""Control handling for runs with or without in-run controls.

Patient runs on this platform may carry NO controls. Instead a scheduled
control run (extraction blank + mock community) produces a control summary
JSON that later patient runs reference with --control_summary. Patient results
are released only while that summary is PASS and not older than
--max_age_days.

Outcomes (control_status.status):
  PASS     in-run or referenced controls within limits and fresh
  FAIL     controls outside limits
  EXPIRED  referenced controls older than --max_age_days
  MISSING  no controls available at all
"""
import argparse
import csv
import datetime as dt
import glob
import math
import os

import gutlib as g


def load_species(d, sample):
    p = os.path.join(d, "%s.species.tsv" % sample)
    return g.read_tsv(p) if os.path.exists(p) else []


def kept(rows):
    return [r for r in rows if str(r.get("kept")) == "True"]


def bray_curtis(x, y):
    keys = set(x) | set(y)
    num = sum(abs(x.get(k, 0.0) - y.get(k, 0.0)) for k in keys)
    den = sum(x.get(k, 0.0) + y.get(k, 0.0) for k in keys)
    return num / den if den else 1.0


def summarize(sheet, species_dir, expected_path, a):
    blanks, mocks = [], []
    expected = {}
    if expected_path:
        for r in g.read_tsv(expected_path):
            expected[r["taxon"]] = g.fnum(r["expected_rel_abundance"])
        tot = sum(expected.values())
        expected = {k: v / tot for k, v in expected.items()} if tot else expected
    for r in sheet:
        rows = kept(load_species(species_dir, r["alias"]))
        obs = {x["taxon"]: g.fnum(x["final_rel_abundance"]) for x in rows}
        if r["type"] in ("negative_control", "no_template_control"):
            blanks.append({
                "sample": r["alias"],
                "contaminants": [{"taxon": x["taxon"], "reads": g.fnum(x["final_reads"]),
                                  "rel_abundance": g.fnum(x["final_rel_abundance"])}
                                 for x in rows if g.fnum(x["final_reads"]) >= a.contam_min_reads],
            })
        elif r["type"] == "positive_control" and expected:
            bc = bray_curtis(obs, expected)
            unexpected = sum(v for k, v in obs.items() if k not in expected)
            missing = [k for k in expected if obs.get(k, 0.0) <= 0]
            fold = {}
            for k, ev in expected.items():
                ov = obs.get(k, 0.0)
                fold[k] = math.log2(ov / ev) if ov > 0 and ev > 0 else None
            ok = bc <= a.mock_max_bray and unexpected <= a.mock_max_unexpected and not missing
            mocks.append({"sample": r["alias"], "bray_curtis": bc,
                          "unexpected_abundance": unexpected, "missing_expected": missing,
                          "log2_fold_error": fold, "pass": bool(ok)})
    status = "PASS"
    if any(not m["pass"] for m in mocks):
        status = "FAIL"
    if not blanks and not mocks:
        return None
    return {"control_date": a.control_date, "pipeline_version": a.pipeline_version,
            "blanks": blanks, "mocks": mocks, "status": status,
            "limits": {"mock_max_bray": a.mock_max_bray,
                       "mock_max_unexpected": a.mock_max_unexpected}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--species_dir", default=".")
    ap.add_argument("--mock_expected", default=None, help="TSV: taxon, expected_rel_abundance")
    ap.add_argument("--control_summary", default=None, help="JSON from an earlier control run")
    ap.add_argument("--control_date", default=dt.date.today().isoformat())
    ap.add_argument("--pipeline_version", default="unknown")
    ap.add_argument("--max_age_days", type=int, default=31)
    ap.add_argument("--mock_max_bray", type=float, default=0.30)
    ap.add_argument("--mock_max_unexpected", type=float, default=0.05)
    ap.add_argument("--contam_min_reads", type=float, default=50)
    ap.add_argument("--out_status", required=True)
    ap.add_argument("--out_flags", required=True)
    ap.add_argument("--out_summary", required=True)
    a = ap.parse_args()

    sheet = list(csv.DictReader(open(a.sheet)))
    inrun = summarize(sheet, a.species_dir, a.mock_expected, a)
    source, age = "none", None
    summ = None
    if inrun:
        summ, source, age = inrun, "in_run", 0
    elif a.control_summary and os.path.getsize(a.control_summary) > 2:
        summ, source = g.read_json(a.control_summary), "referenced"
        try:
            age = (dt.date.today() - dt.date.fromisoformat(summ["control_date"])).days
        except Exception:
            age = None

    if summ is None:
        status, reason = "MISSING", "No in-run controls and no control summary supplied."
    elif summ.get("status") == "FAIL":
        status, reason = "FAIL", "Control run outside limits."
    elif age is None or age > a.max_age_days:
        status, reason = "EXPIRED", "Control run is older than %d days." % a.max_age_days
    else:
        status, reason = "PASS", "Controls within limits (%s, %s days old)." % (source, age)

    g.write_json({"status": status, "reason": reason, "source": source,
                  "age_days": age, "max_age_days": a.max_age_days,
                  "control_date": (summ or {}).get("control_date"),
                  "release_patient_results": status == "PASS"}, a.out_status)
    if summ:
        g.write_json(summ, a.out_summary)
    else:
        g.write_json({}, a.out_summary)

    # Flag patient taxa that match the control run's contaminant list.
    contam = {}
    for b in (summ or {}).get("blanks", []):
        for c in b["contaminants"]:
            contam[c["taxon"]] = max(contam.get(c["taxon"], 0.0), c["rel_abundance"])
    flags = []
    for r in sheet:
        if r["type"] != "test_sample":
            continue
        for x in kept(load_species(a.species_dir, r["alias"])):
            if x["taxon"] in contam:
                flags.append({"sample": r["alias"], "taxon": x["taxon"],
                              "sample_rel_abundance": x["final_rel_abundance"],
                              "blank_rel_abundance": contam[x["taxon"]],
                              "ratio": (g.fnum(x["final_rel_abundance"]) / contam[x["taxon"]]
                                        if contam[x["taxon"]] else "")})
    g.write_tsv(flags, a.out_flags, ["sample", "taxon", "sample_rel_abundance",
                                     "blank_rel_abundance", "ratio"])


if __name__ == "__main__":
    main()
