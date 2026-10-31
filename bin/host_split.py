#!/usr/bin/env python3
"""Split reads into host and non-host using minimap2's PAF output (run with -c, so the
alignment is base-level). Reads FASTQ on stdin and writes the NON-HOST reads to stdout.

Only the NON-HOST reads are written to disk. Host reads are counted and
discarded, so no human sequence leaves this step (donor privacy; also covers
human PGx reads carried over from a previous library on a washed flow cell).

A read is "host" when its primary alignment (the first PAF line for the read) covers at
least --min_aligned_frac of the read and mapq >= --min_mapq. The aligned part is the query
span of the alignment, which equals the M/I/=/X bases of its CIGAR. Partial alignments are
kept as non-host so that microbial reads with short human-like segments are not
lost (dynamic alignment-length criterion).

Optional --pgx_bed: BED of human PGx target regions (same coordinates as the
host reference). Host reads overlapping these regions are counted as likely
carryover from the earlier PGx library.
"""
import argparse
import bisect
import sys

import gutlib as g



def load_bed(path):
    iv = {}
    if not path:
        return iv
    with open(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith(("#", "track", "browser")):
                continue
            f = line.split("\t")
            iv.setdefault(f[0], []).append((int(f[1]), int(f[2])))
    for k in iv:
        iv[k].sort()
    return iv


def overlaps(iv, chrom, start, end):
    lst = iv.get(chrom)
    if not lst:
        return False
    i = bisect.bisect_left(lst, (start, 0))
    for j in range(max(0, i - 50), min(len(lst), i + 50)):
        s, e = lst[j]
        if s < end and e > start:
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paf", required=True, help="minimap2 -c --secondary=no PAF against the host reference")
    ap.add_argument("--stats", required=True, help="output JSON")
    ap.add_argument("--sample", required=True)
    ap.add_argument("--min_aligned_frac", type=float, default=0.5)
    ap.add_argument("--min_mapq", type=int, default=0)
    ap.add_argument("--pgx_bed", default=None)
    ap.add_argument("--carryover_warn_reads", type=int, default=100)
    a = ap.parse_args()

    bed = load_bed(a.pgx_bed)
    host_ids = set()
    seen = set()
    host = partial = carry = 0
    with open(a.paf) as fh:
        for line in fh:
            f = line.split("\t", 12)
            qname = f[0]
            if qname in seen:  # supplementary alignments follow the primary
                continue
            seen.add(qname)
            qlen, qstart, qend, mapq = int(f[1]), int(f[2]), int(f[3]), int(f[11])
            if (qend - qstart) / max(qlen, 1) >= a.min_aligned_frac and mapq >= a.min_mapq:
                host_ids.add(qname)
                host += 1
                if overlaps(bed, f[5], int(f[7]), int(f[8])):
                    carry += 1
            else:
                partial += 1

    total = nonhost = 0
    out = sys.stdout
    lines = iter(sys.stdin)
    for header in lines:
        seq, plus, qual = next(lines), next(lines), next(lines)
        total += 1
        qname = header[1:].split(None, 1)[0]
        if qname in host_ids:
            continue
        out.write(f"@{qname}\n{seq}+\n{qual}")
        nonhost += 1

    stats = {
        "sample": a.sample,
        "total_reads": total,
        "host_reads": host,
        "host_partial_kept_reads": partial,
        "nonhost_reads": nonhost,
        "host_fraction": host / total if total else 0.0,
        "pgx_carryover_reads": carry,
        "pgx_carryover_flag": bool(carry >= a.carryover_warn_reads),
        "pgx_bed_used": bool(a.pgx_bed),
    }
    g.write_json(stats, a.stats)


if __name__ == "__main__":
    main()
