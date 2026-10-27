#!/usr/bin/env python3
"""Validate (or auto-create) the sample sheet.

Columns (EPI2ME convention): barcode, alias, type [, any extra metadata].
type: test_sample | positive_control | negative_control | no_template_control
Extra columns are carried through (for example group, subject_id,
collection_date, extraction_lot, bristol_score, time_to_freezing_h).
"""
import argparse
import csv
import re
import sys

ALLOWED_TYPES = {"test_sample", "positive_control", "negative_control",
                 "no_template_control"}
REQUIRED = ["barcode", "alias", "type"]


def die(msg):
    sys.stderr.write("SAMPLE SHEET ERROR: %s\n" % msg)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--found", required=True,
                    help="comma separated sample ids discovered in the input")
    ap.add_argument("--sample_sheet", default=None)
    ap.add_argument("--pgx_barcodes", default="",
                    help="barcodes used by the previous (PGx) library")
    ap.add_argument("--required_fields", default="",
                    help="comma separated extra columns that must be filled")
    ap.add_argument("--out", required=True)
    ap.add_argument("--warnings", required=True)
    a = ap.parse_args()

    found = [x for x in a.found.split(",") if x]
    pgx = {x.strip().lower() for x in a.pgx_barcodes.split(",") if x.strip()}
    warnings = []

    if a.sample_sheet:
        with open(a.sample_sheet, newline="") as fh:
            sniff = fh.read(2048)
            fh.seek(0)
            delim = "\t" if sniff.count("\t") > sniff.count(",") else ","
            rows = list(csv.DictReader(fh, delimiter=delim))
            cols = rows[0].keys() if rows else []
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            die("missing required column(s): %s" % ", ".join(missing))
    else:
        rows = [{"barcode": s, "alias": s, "type": "test_sample"} for s in found]
        cols = REQUIRED
        warnings.append("No sample sheet supplied: every input is treated as a "
                        "test_sample and named by its barcode or folder.")

    seen_alias, seen_bc, out_rows = set(), set(), []
    extra = [c for c in cols if c not in REQUIRED]
    req_extra = [c.strip() for c in a.required_fields.split(",") if c.strip()]
    for c in req_extra:
        if c not in cols:
            die("required metadata column '%s' is not in the sample sheet" % c)

    for i, r in enumerate(rows, start=2):
        bc = (r.get("barcode") or "").strip()
        al = (r.get("alias") or "").strip()
        ty = (r.get("type") or "").strip()
        if not bc or not al or not ty:
            die("row %d: barcode, alias and type must all be filled" % i)
        if ty not in ALLOWED_TYPES:
            die("row %d: type '%s' not in %s" % (i, ty, sorted(ALLOWED_TYPES)))
        if not re.fullmatch(r"[A-Za-z0-9._\-]+", al):
            die("row %d: alias '%s' may only contain letters, digits, . _ -" % (i, al))
        if al in seen_alias:
            die("duplicate alias '%s'" % al)
        if bc in seen_bc:
            die("duplicate barcode '%s'" % bc)
        seen_alias.add(al)
        seen_bc.add(bc)
        if bc.lower() in pgx:
            die("barcode '%s' was used by the previous PGx library on this "
                "flow cell. Use different barcodes to avoid carryover "
                "misassignment." % bc)
        for c in req_extra:
            if not (r.get(c) or "").strip():
                die("row %d (%s): required metadata '%s' is empty" % (i, al, c))
        for c in extra:
            v = r.get(c) or ""
            if re.search(r"[^\w\s.,:;/()\-+%]", v):
                die("row %d (%s): column '%s' contains special characters" % (i, al, c))
        row = {"barcode": bc, "alias": al, "type": ty}
        for c in extra:
            row[c] = (r.get(c) or "").strip()
        out_rows.append(row)

    if not any(r["type"] == "test_sample" for r in out_rows):
        die("the sample sheet has no test_sample rows")

    missing_inputs = [r["barcode"] for r in out_rows if r["barcode"] not in found]
    if missing_inputs:
        warnings.append("In sample sheet but no data found: %s" % ", ".join(missing_inputs))
    unlisted = [f for f in found if f not in seen_bc]
    if unlisted:
        warnings.append("Data found but not in sample sheet (ignored): %s" % ", ".join(unlisted))
    if not any(r["type"] != "test_sample" for r in out_rows):
        warnings.append("No control samples in this run. Patient results depend "
                        "on a recent scheduled control run (see control status).")

    # Only keep rows that have data.
    out_rows = [r for r in out_rows if r["barcode"] in found]
    if not out_rows:
        die("none of the sample sheet barcodes match the input data")

    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REQUIRED + extra)
        w.writeheader()
        w.writerows(out_rows)
    with open(a.warnings, "w") as fh:
        fh.write("\n".join(warnings) + ("\n" if warnings else ""))


if __name__ == "__main__":
    main()
