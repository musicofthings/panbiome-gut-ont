#!/usr/bin/env python3
"""Create tiny synthetic ONT input for smoke tests (not biologically meaningful)."""
import gzip, os, random, sys

out = sys.argv[1] if len(sys.argv) > 1 else "test_data"
rng = random.Random(7)
for bc in ("barcode01", "barcode02", "barcode03"):
    d = os.path.join(out, "fastq_pass", bc)
    os.makedirs(d, exist_ok=True)
    with gzip.open(os.path.join(d, "reads_0.fastq.gz"), "wt") as fh:
        for i in range(40):
            s = "".join(rng.choice("ACGT") for _ in range(rng.randint(800, 2500)))
            fh.write("@%s_%d runid=TESTRUN flow_cell_id=TESTFC barcode=%s "
                     "basecall_model_version_id=dna_r10.4.1_e8.2_400bps_sup@v5.0.0\n%s\n+\n%s\n"
                     % (bc, i, bc, s, "5" * len(s)))
with open(os.path.join(out, "sample_sheet.csv"), "w") as fh:
    fh.write("barcode,alias,type,group\n"
             "barcode01,P001,test_sample,A\nbarcode02,P002,test_sample,B\nbarcode03,BLANK1,negative_control,\n")
emu = os.path.join(out, "stub_db", "emu")
os.makedirs(emu, exist_ok=True)
with open(os.path.join(emu, "emu_stub.txt"), "w") as fh:
    fh.write("stub emu database for -stub-run only\n")
with open(os.path.join(out, "control_summary.json"), "w") as fh:
    fh.write('{"control_date":"2026-10-27","pipeline_version":"0.1.0",'
             '"blanks":[],"mocks":[],"status":"PASS",'
             '"limits":{"mock_max_bray":0.30,"mock_max_unexpected":0.05}}\n')
