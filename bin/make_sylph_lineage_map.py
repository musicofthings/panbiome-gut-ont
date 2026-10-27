#!/usr/bin/env python3
"""Build the genome->lineage map used by parse_profiles.py sylph.

Input: GTDB taxonomy files (bac120_taxonomy_rXXX.tsv, ar53_taxonomy_rXXX.tsv).
Lines look like:  RS_GCF_000005845.2<TAB>d__Bacteria;p__...;s__Escherichia coli
Output: <accession><TAB><lineage>  with the RS_/GB_ prefix removed, matching
the GCF_/GCA_ accession found in the sylph database genome file names.

Usage: make_sylph_lineage_map.py bac120_taxonomy.tsv ar53_taxonomy.tsv > map.tsv
"""
import re
import sys


def main(paths):
    for p in paths:
        with open(p) as fh:
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) < 2:
                    continue
                acc = re.sub(r"^(RS|GB)_", "", f[0])
                print("%s\t%s" % (acc, f[1]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
