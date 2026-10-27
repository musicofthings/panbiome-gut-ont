"""Shared helpers for the panbiome-gut-ont helper scripts."""
import csv
import gzip
import json
import math
import re
import sys

import numpy as np

# Error probability lookup for Phred+33 characters (index = Phred score).
ERR = np.array([10 ** (-i / 10.0) for i in range(0, 94)])

SPECIES_COLS = [
    "taxon", "lineage", "reads", "rel_abundance", "method", "ani", "coverage",
]


def open_text(path, mode="rt"):
    return gzip.open(path, mode) if str(path).endswith(".gz") else open(path, mode)


def read_fastq(path):
    """Yield (header_without_at, seq, qual) from a FASTQ(.gz)."""
    with open_text(path) as fh:
        while True:
            h = fh.readline()
            if not h:
                return
            s = fh.readline().rstrip("\n")
            fh.readline()
            q = fh.readline().rstrip("\n")
            if not s and not q:
                return
            yield h.rstrip("\n")[1:], s, q


def qual_to_err(qual):
    """Mean per-base error probability of a quality string (numpy, fast)."""
    arr = np.frombuffer(qual.encode("ascii"), dtype=np.uint8).astype(np.int16) - 33
    arr = np.clip(arr, 0, 93)
    return float(ERR[arr].mean()) if arr.size else 1.0


def err_to_q(err):
    return -10.0 * math.log10(err) if err > 0 else 60.0


def n50(lengths):
    if not lengths:
        return 0
    ls = sorted(lengths, reverse=True)
    half = sum(ls) / 2.0
    acc = 0
    for x in ls:
        acc += x
        if acc >= half:
            return x
    return ls[-1]


def parse_header_kv(header):
    """Parse key=value tokens from a MinKNOW/Dorado FASTQ header."""
    kv = {}
    for tok in header.split()[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            kv[k] = v
    return kv


MODEL_RE = re.compile(r"_(fast|hac|sup)@v?([0-9][0-9A-Za-z.\-]*)")


def classify_model(model_id):
    """Return (tier, version) from a basecall model id, e.g. sup / 5.0.0."""
    if not model_id:
        return "unknown", ""
    m = MODEL_RE.search(model_id)
    if m:
        return m.group(1), m.group(2)
    low = model_id.lower()
    for tier in ("sup", "hac", "fast"):
        if tier in low:
            return tier, ""
    return "unknown", ""


def write_json(obj, path):
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, default=float)


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def read_tsv(path, delimiter="\t"):
    with open_text(path) as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def write_tsv(rows, path, fieldnames, delimiter="\t"):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=delimiter,
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def fnum(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def species_from_lineage(lineage):
    for part in lineage.split(";"):
        if part.startswith("s__"):
            return part[3:]
    return ""


def norm_taxon(name):
    return re.sub(r"\s+", " ", name.strip()).lower()


def die(msg):
    sys.stderr.write("ERROR: %s\n" % msg)
    sys.exit(1)
