#!/usr/bin/env bash
# Dry-run the whole DAG without any tools or databases (needs only Nextflow).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 test_data/make_test_data.py test_data
nextflow run main.nf -stub-run -profile test \
  --fastq test_data/fastq_pass --sample_sheet test_data/sample_sheet.csv \
  --host_ref test_data/stub_db/host.mmi --kraken2_db test_data/stub_db/kraken2 \
  --out_dir "${1:-stub_output}"
test -s "${1:-stub_output}/wf-gut-report.html"
echo "stub run OK"
