#!/usr/bin/env python3
"""Split a minimap2 SAM stream (stdin) into host and non-host reads.

Only the NON-HOST reads are written to disk. Host reads are counted and
discarded, so no human sequence leaves this step (donor privacy; also covers
human PGx reads carried over from a previous library on a washed flow cell).

A read is "host" when its primary alignment covers at least
--min_aligned_frac of the read and mapq >= --min_mapq. Partial alignments are
kept as non-host so that microbial reads with short human-like segments are not
lost (dynamic alignment-length criterion).

Optional --pgx_bed: BED of human PGx target regions (same coordinates as the
host reference). Host reads overlapping these regions are counted as likely
carryover from the earlier PGx library.
"""
import argparse
import bisect
import gzip
import re
import sys

import gutlib as g

CIGAR_RE = re.compile(r"(\d+)([MIDNSHP=X])")
COMP = str.maketrans("ACGTNacgtn", "TGCANtgcan")


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
    ap.add_argument("--nonhost", required=True, help="output FASTQ.gz")
    ap.add_argument("--stats", required=True, help="output JSON")
    ap.add_argument("--sample", required=True)
    ap.add_argument("--min_aligned_frac", type=float, default=0.5)
    ap.add_argument("--min_mapq", type=int, default=0)
    ap.add_argument("--pgx_bed", default=None)
    ap.add_argument("--carryover_warn_reads", type=int, default=100)
    a = ap.parse_args()

    bed = load_bed(a.pgx_bed)
    total = host = partial = nonhost = carry = 0
    with gzip.open(a.nonhost, "wt") as out:
        for line in sys.stdin:
            if line.startswith("@"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 11:
                continue
            flag = int(f[1])
            if flag & 0x900:  # secondary / supplementary
                continue
            total += 1
            qname, rname, pos, mapq = f[0], f[2], int(f[3]), int(f[4])
            cigar, seq, qual = f[5], f[9], f[10]
            is_host = False
            if not flag & 4 and cigar != "*" and seq != "*":
                q_aln = ref_len = 0
                for n, op in CIGAR_RE.findall(cigar):
                    n = int(n)
                    if op in "M=XI":
                        q_aln += n
                    if op in "M=XDN":
                        ref_len += n
                frac = q_aln / max(len(seq), 1)
                if frac >= a.min_aligned_frac and mapq >= a.min_mapq:
                    is_host = True
                    host += 1
                    if overlaps(bed, rname, pos - 1, pos - 1 + ref_len):
                        carry += 1
                else:
                    partial += 1
            if is_host:
                continue
            if seq == "*":
                continue
            if flag & 16:
                seq = seq.translate(COMP)[::-1]
                qual = qual[::-1]
            if qual == "*":
                qual = "I" * len(seq)
            out.write("@%s\n%s\n+\n%s\n" % (qname, seq, qual))
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
