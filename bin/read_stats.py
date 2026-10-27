#!/usr/bin/env python3
"""Per-sample read statistics for ONT FASTQ.

Mean quality is computed on the error-probability scale (the correct way),
not as an average of Phred scores. Also reports:
  * basecall model tier (fast / hac / sup) parsed from read headers
  * residual ONT adapter prevalence at read ends
  * length and quality histograms
"""
import argparse
import re
import statistics
from collections import Counter

import gutlib as g

# Native-barcoding / ligation adapter (top strand) and its reverse complement.
ADAPTERS = ["AATGTACTTCGTTCAGTTACGTATTGCT"]
K = 12


def revcomp(s):
    return s[::-1].translate(str.maketrans("ACGTN", "TGCAN"))


def kmers(seq, k=K):
    return {seq[i:i + k] for i in range(len(seq) - k + 1)}


def build_adapter_kmers(extra_fasta=None):
    seqs = list(ADAPTERS)
    if extra_fasta:
        with open(extra_fasta) as fh:
            cur = []
            for line in fh:
                if line.startswith(">"):
                    if cur:
                        seqs.append("".join(cur))
                    cur = []
                else:
                    cur.append(line.strip().upper())
            if cur:
                seqs.append("".join(cur))
    ks = set()
    for s in seqs:
        ks |= kmers(s)
        ks |= kmers(revcomp(s))
    return ks


def adapter_hit(window, ak, min_shared=4):
    return len(kmers(window.upper()) & ak) >= min_shared


def model_from_bam_header(path):
    models = Counter()
    try:
        with open(path) as fh:
            for line in fh:
                m = re.search(r"basecall_model=([^\s;]+)", line)
                if m:
                    models[m.group(1)] += 1
    except FileNotFoundError:
        pass
    return models


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fastq", required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--stage", default="raw")
    ap.add_argument("--json", required=True)
    ap.add_argument("--bam_header", default=None)
    ap.add_argument("--adapters_fasta", default=None)
    ap.add_argument("--adapter_reads", type=int, default=20000)
    ap.add_argument("--window", type=int, default=100)
    a = ap.parse_args()

    ak = build_adapter_kmers(a.adapters_fasta)
    lengths, read_qs = [], []
    err_sum, base_sum = 0.0, 0
    models, runs, cells, barcodes = Counter(), set(), set(), Counter()
    checked = ad5 = ad3 = adany = 0
    len_hist, q_hist = Counter(), Counter()

    for hdr, seq, qual in g.read_fastq(a.fastq):
        n = len(seq)
        if n == 0:
            continue
        lengths.append(n)
        e = g.qual_to_err(qual)
        err_sum += e * n
        base_sum += n
        rq = g.err_to_q(e)
        read_qs.append(rq)
        len_hist[min(n // 500, 20) * 500] += 1
        q_hist[min(int(rq), 40)] += 1
        if len(lengths) <= 2000:
            kv = g.parse_header_kv(hdr)
            if "basecall_model_version_id" in kv:
                models[kv["basecall_model_version_id"]] += 1
            if "runid" in kv:
                runs.add(kv["runid"])
            if "flow_cell_id" in kv:
                cells.add(kv["flow_cell_id"])
            if "barcode" in kv:
                barcodes[kv["barcode"]] += 1
        if checked < a.adapter_reads and n >= 2 * a.window:
            checked += 1
            h5 = adapter_hit(seq[:a.window], ak)
            h3 = adapter_hit(seq[-a.window:], ak)
            ad5 += h5
            ad3 += h3
            adany += (h5 or h3)

    if a.bam_header:
        models.update(model_from_bam_header(a.bam_header))

    top_model = models.most_common(1)[0][0] if models else ""
    tier, version = g.classify_model(top_model)
    reads = len(lengths)
    out = {
        "sample": a.sample,
        "stage": a.stage,
        "reads": reads,
        "bases": base_sum,
        "gb": base_sum / 1e9,
        "mean_len": (base_sum / reads) if reads else 0,
        "median_len": statistics.median(lengths) if reads else 0,
        "n50": g.n50(lengths),
        "min_len": min(lengths) if reads else 0,
        "max_len": max(lengths) if reads else 0,
        "mean_q": g.err_to_q(err_sum / base_sum) if base_sum else 0.0,
        "median_read_q": statistics.median(read_qs) if reads else 0.0,
        "pct_q10": 100.0 * sum(1 for q in read_qs if q >= 10) / reads if reads else 0.0,
        "pct_q15": 100.0 * sum(1 for q in read_qs if q >= 15) / reads if reads else 0.0,
        "basecall_model": top_model,
        "basecall_tier": tier,
        "basecall_version": version,
        "run_ids": sorted(runs),
        "flow_cell_ids": sorted(cells),
        "header_barcodes": dict(barcodes),
        "adapter_reads_checked": checked,
        "adapter_5p_pct": 100.0 * ad5 / checked if checked else 0.0,
        "adapter_3p_pct": 100.0 * ad3 / checked if checked else 0.0,
        "adapter_any_pct": 100.0 * adany / checked if checked else 0.0,
        "length_hist": {str(k): v for k, v in sorted(len_hist.items())},
        "qual_hist": {str(k): v for k, v in sorted(q_hist.items())},
    }
    g.write_json(out, a.json)


if __name__ == "__main__":
    main()
