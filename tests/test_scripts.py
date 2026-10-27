"""End-to-end tests of the helper scripts on small synthetic data.

Run:  python -m pytest tests -q
"""
import csv
import gzip
import json
import os
import random
import subprocess
import sys

import pytest

BIN = os.path.join(os.path.dirname(__file__), "..", "bin")


def run(script, *args, cwd=None, stdin=None):
    p = subprocess.run([sys.executable, os.path.join(BIN, script), *map(str, args)],
                       cwd=cwd, input=stdin, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p


def rand_seq(n, rng):
    return "".join(rng.choice("ACGT") for _ in range(n))


def write_fastq(path, n, rng, model="dna_r10.4.1_e8.2_400bps_sup@v5.0.0", adapter=False, q="I"):
    ad = "AATGTACTTCGTTCAGTTACGTATTGCT"
    with gzip.open(path, "wt") as fh:
        for i in range(n):
            s = rand_seq(rng.randint(1500, 4000), rng)
            if adapter and i % 2 == 0:
                s = ad + s
            fh.write("@r%d runid=RUN1 flow_cell_id=PAS1 barcode=barcode01 basecall_model_version_id=%s\n%s\n+\n%s\n"
                     % (i, model, s, q * len(s)))


def write_tsv(path, rows, cols):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def test_read_stats(tmp_path):
    rng = random.Random(1)
    fq = tmp_path / "a.fastq.gz"
    write_fastq(fq, 200, rng, adapter=True, q="+")  # Q10
    run("read_stats.py", "--fastq", fq, "--sample", "s1", "--json", tmp_path / "o.json")
    d = json.load(open(tmp_path / "o.json"))
    assert d["reads"] == 200 and d["basecall_tier"] == "sup" and d["basecall_version"] == "5.0.0"
    assert abs(d["mean_q"] - 10.0) < 0.01
    assert d["adapter_any_pct"] > 30


def test_read_stats_fast_model(tmp_path):
    rng = random.Random(2)
    fq = tmp_path / "a.fastq.gz"
    write_fastq(fq, 20, rng, model="dna_r10.4.1_e8.2_400bps_fast@v4.3.0")
    run("read_stats.py", "--fastq", fq, "--sample", "s1", "--json", tmp_path / "o.json")
    assert json.load(open(tmp_path / "o.json"))["basecall_tier"] == "fast"


def test_samplesheet_ok_and_errors(tmp_path):
    sh = tmp_path / "s.csv"
    sh.write_text("barcode,alias,type,group\nbarcode01,P001,test_sample,A\nbarcode02,P002,test_sample,B\n"
                  "barcode03,BLANK1,negative_control,\n")
    run("validate_samplesheet.py", "--found", "barcode01,barcode02,barcode03", "--sample_sheet", sh,
        "--out", tmp_path / "v.csv", "--warnings", tmp_path / "w.txt")
    rows = list(csv.DictReader(open(tmp_path / "v.csv")))
    assert len(rows) == 3 and rows[0]["group"] == "A"
    # barcode used by the earlier PGx library must be rejected
    p = subprocess.run([sys.executable, os.path.join(BIN, "validate_samplesheet.py"), "--found",
                        "barcode01,barcode02,barcode03", "--sample_sheet", str(sh), "--pgx_barcodes",
                        "barcode02", "--out", str(tmp_path / "v2.csv"), "--warnings", str(tmp_path / "w2.txt")],
                       capture_output=True, text=True)
    assert p.returncode != 0 and "PGx" in p.stderr
    # no sample sheet -> auto-created with a warning
    run("validate_samplesheet.py", "--found", "barcode01,barcode02", "--out", tmp_path / "v3.csv",
        "--warnings", tmp_path / "w3.txt")
    assert "No sample sheet" in open(tmp_path / "w3.txt").read()


def sam_line(name, flag, rname, pos, cigar, seq):
    return "\t".join([name, str(flag), rname, str(pos), "60", cigar, "*", "0", "0", seq, "I" * len(seq)]) + "\n"


def test_host_split(tmp_path):
    rng = random.Random(3)
    bed = tmp_path / "pgx.bed"
    bed.write_text("chr1\t1000\t2000\n")
    s100 = rand_seq(100, rng)
    sam = "@HD\tVN:1.6\n"
    sam += sam_line("host_pgx", 0, "chr1", 1500, "100M", s100)       # host, in PGx region
    sam += sam_line("host_other", 16, "chr2", 5000, "100M", s100)    # host, elsewhere
    sam += sam_line("partial", 0, "chr1", 100, "20M80S", s100)       # 20% aligned -> kept
    sam += sam_line("micro", 4, "*", 0, "*", s100)                   # unmapped -> kept
    run("host_split.py", "--nonhost", tmp_path / "nh.fq.gz", "--stats", tmp_path / "h.json", "--sample", "s1",
        "--pgx_bed", bed, "--carryover_warn_reads", 1, stdin=sam)
    st = json.load(open(tmp_path / "h.json"))
    assert st["host_reads"] == 2 and st["nonhost_reads"] == 2 and st["pgx_carryover_reads"] == 1
    assert st["pgx_carryover_flag"] is True
    names = [l[1:].strip() for i, l in enumerate(gzip.open(tmp_path / "nh.fq.gz", "rt")) if i % 4 == 0]
    assert sorted(names) == ["micro", "partial"]


KREPORT = (" 10.00\t100\t0\tR\t1\troot\n"
           " 10.00\t100\t0\tD\t2\t  Bacteria\n"
           "  5.00\t60\t0\tG\t10\t    Escherichia\n"
           "  5.00\t60\t60\tS\t11\t      Escherichia coli\n"
           "  3.00\t40\t0\tG\t20\t    Bacteroides\n"
           "  3.00\t40\t40\tS\t21\t      Bacteroides fragilis\n")
BRACKEN = ("name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\tadded_reads\tnew_est_reads\tfraction_total_reads\n"
           "Escherichia coli\t11\tS\t60\t10\t70\t0.7\nBacteroides fragilis\t21\tS\t40\t-10\t30\t0.3\n")


def test_profiles_and_reconcile(tmp_path):
    (tmp_path / "k.report").write_text(KREPORT)
    (tmp_path / "k.bracken").write_text(BRACKEN)
    run("parse_profiles.py", "kraken", "--kreport", tmp_path / "k.report", "--bracken", tmp_path / "k.bracken",
        "--out", tmp_path / "kr.tsv", "--krona", tmp_path / "krona.txt")
    rows = list(csv.DictReader(open(tmp_path / "kr.tsv"), delimiter="\t"))
    assert rows[0]["taxon"] == "Escherichia coli" and "g__Escherichia" in rows[0]["lineage"]
    assert "Bacteroides fragilis" in open(tmp_path / "krona.txt").read()

    (tmp_path / "map.tsv").write_text("GCF_000005845.2\td__Bacteria;g__Escherichia;s__Escherichia coli\n"
                                      "GCF_000025985.1\td__Bacteria;g__Bacteroides;s__Bacteroides fragilis\n")
    (tmp_path / "sylph.tsv").write_text(
        "Sample_file\tGenome_file\tTaxonomic_abundance\tSequence_abundance\tAdjusted_ANI\tEff_cov\n"
        "r.fq\t/db/GCF_000005845.2_genomic.fna.gz\t80\t80\t98.5\t10\n"
        "r.fq\t/db/GCF_000999999.1_genomic.fna.gz\t20\t20\t97.0\t2\n")
    run("parse_profiles.py", "sylph", "--tsv", tmp_path / "sylph.tsv", "--lineage_map", tmp_path / "map.tsv",
        "--out", tmp_path / "sy.tsv")
    (tmp_path / "watch.tsv").write_text("taxon\tmin_rel_abundance\tnote\nEscherichia coli\t0.5\ttest\n")
    run("reconcile_taxa.py", "--sample", "s1", "--bracken", tmp_path / "kr.tsv", "--sylph", tmp_path / "sy.tsv",
        "--watchlist", tmp_path / "watch.tsv", "--out", tmp_path / "sp.tsv", "--watch_out", tmp_path / "wl.tsv",
        "--json", tmp_path / "sp.json")
    sp = {r["taxon"]: r for r in csv.DictReader(open(tmp_path / "sp.tsv"), delimiter="\t")}
    assert sp["Escherichia coli"]["kept"] == "True" and sp["Escherichia coli"]["evidence"] == "bracken+sylph"
    assert sp["Bacteroides fragilis"]["kept"] == "False"      # only one method supports it
    assert abs(float(sp["Escherichia coli"]["final_rel_abundance"]) - 1.0) < 1e-9
    wl = list(csv.DictReader(open(tmp_path / "wl.tsv"), delimiter="\t"))
    assert wl[0]["flag"] == "ALERT"


def make_species(path, taxa_abund, total=100000):
    rows = [{"taxon": t, "lineage": "", "evidence": "bracken+sylph", "n_methods": 2, "bracken_reads": int(a * total),
             "bracken_rel": a, "sylph_rel": a, "sylph_ani": 99, "sylph_cov": 5, "emu_rel": "", "kept": True,
             "final_reads": int(a * total), "final_rel_abundance": a} for t, a in taxa_abund.items()]
    write_tsv(path, rows, ["taxon", "lineage", "evidence", "n_methods", "bracken_reads", "bracken_rel", "sylph_rel",
                           "sylph_ani", "sylph_cov", "emu_rel", "kept", "final_reads", "final_rel_abundance"])


def test_controls_diversity_qc_report(tmp_path):
    d = tmp_path
    sheet = ["barcode,alias,type,group"]
    allsp = {}
    rng = random.Random(5)
    base = ["Bacteroides a", "Prevotella b", "Faecalibacterium c", "Escherichia coli", "Akkermansia d"]
    for i in range(8):
        w = [rng.random() + (2 if (i % 2 and t == "Prevotella b") else 0) for t in base]
        s = sum(w)
        ab = {t: x / s for t, x in zip(base, w)}
        allsp["P%d" % i] = ab
        sheet.append("barcode%02d,P%d,test_sample,%s" % (i, i, "A" if i % 2 else "B"))
        make_species(d / ("P%d.species.tsv" % i), ab)
    sheet.append("barcode20,MOCK1,positive_control,")
    sheet.append("barcode21,BLANK1,negative_control,")
    make_species(d / "MOCK1.species.tsv", {"Bacteroides a": 0.5, "Escherichia coli": 0.5})
    make_species(d / "BLANK1.species.tsv", {"Escherichia coli": 1.0}, total=200)
    (d / "sample_sheet.validated.csv").write_text("\n".join(sheet) + "\n")
    (d / "mock.tsv").write_text("taxon\texpected_rel_abundance\nBacteroides a\t0.5\nEscherichia coli\t0.5\n")

    run("control_eval.py", "--sheet", d / "sample_sheet.validated.csv", "--species_dir", d,
        "--mock_expected", d / "mock.tsv", "--out_status", d / "control_status.json",
        "--out_flags", d / "control_contaminant_flags.tsv", "--out_summary", d / "control_summary.json")
    st = json.load(open(d / "control_status.json"))
    assert st["status"] == "PASS" and st["release_patient_results"] is True
    flags = list(csv.DictReader(open(d / "control_contaminant_flags.tsv"), delimiter="\t"))
    assert any(f["taxon"] == "Escherichia coli" for f in flags)

    # patient-only run referencing the saved summary; expired when old
    patient_sheet = "\n".join(sheet[:9]) + "\n"
    (d / "patient.csv").write_text(patient_sheet)
    old = json.load(open(d / "control_summary.json"))
    old["control_date"] = "2020-01-01"
    json.dump(old, open(d / "old_summary.json", "w"))
    run("control_eval.py", "--sheet", d / "patient.csv", "--species_dir", d, "--control_summary", d / "old_summary.json",
        "--out_status", d / "st2.json", "--out_flags", d / "f2.tsv", "--out_summary", d / "s2.json")
    assert json.load(open(d / "st2.json"))["status"] == "EXPIRED"
    run("control_eval.py", "--sheet", d / "patient.csv", "--species_dir", d,
        "--out_status", d / "st3.json", "--out_flags", d / "f3.tsv", "--out_summary", d / "s3.json")
    assert json.load(open(d / "st3.json"))["status"] == "MISSING"

    run("diversity.py", "--sheet", d / "sample_sheet.validated.csv", "--species_dir", d, "--outdir", d / "diversity")
    for f in ("alpha_diversity.tsv", "beta_braycurtis.tsv", "feature_table.biom.json", "pcoa_braycurtis.png",
              "rarefaction.png", "abundance_relative.tsv"):
        assert (d / "diversity" / f).exists(), f
    summ = json.load(open(d / "diversity" / "diversity_summary.json"))
    assert summ["n_samples"] == 8 and "permanova_braycurtis" in summ

    # QC inputs
    for i in range(8):
        for stage, gb in (("raw", 3.5), ("filtered", 3.4 if i else 0.9)):
            json.dump({"sample": "P%d" % i, "stage": stage, "reads": 600000, "gb": gb, "bases": gb * 1e9, "n50": 8000,
                       "mean_q": 18.0, "median_read_q": 19.0, "basecall_tier": "sup" if i != 3 else "hac",
                       "basecall_model": "m", "adapter_any_pct": 0.5, "flow_cell_ids": ["PAS1"], "run_ids": ["R1"]},
                      open(d / ("P%d.%s.stats.json" % (i, stage)), "w"))
        json.dump({"sample": "P%d" % i, "host_fraction": 0.01, "nonhost_reads": 590000, "pgx_carryover_reads": 0,
                   "pgx_carryover_flag": False}, open(d / ("P%d.host.json" % i), "w"))
    run("run_qc.py", "--stats_dir", d, "--sheet", d / "patient.csv", "--out_tsv", d / "qc_summary.tsv",
        "--out_json", d / "qc_summary.json")
    qc = {r["sample"]: r for r in csv.DictReader(open(d / "qc_summary.tsv"), delimiter="\t")}
    assert qc["P0"]["status"] == "FAIL" and qc["P3"]["status"] == "WARN" and qc["P1"]["status"] == "PASS"

    # AMR linkage + report
    (d / "amr.tsv").write_text(
        "Protein id\tContig id\tStart\tStop\tStrand\tElement symbol\tElement name\tScope\tType\tSubtype\tClass\tSubclass\t"
        "Method\tTarget length\tReference sequence length\t% Coverage of reference\t% Identity to reference\n"
        "-\tcontig_1\t10\t900\t+\ttet(Q)\ttetracycline resistance\tcore\tAMR\tAMR\tTETRACYCLINE\tTETRACYCLINE\tBLASTX\t300\t300\t100\t100\n"
        "-\tcontig_2\t10\t900\t+\tblaX\tbeta-lactamase\tcore\tAMR\tAMR\tBETA-LACTAM\tBETA-LACTAM\tBLASTX\t300\t300\t60\t99\n")
    (d / "asm.txt").write_text("#seq_name\tlength\tcov.\tcirc.\trepeat\tmult.\talt_group\tgraph_path\ncontig_1\t50000\t12\tY\tN\t1\t*\t1\n")
    (d / "pl.tsv").write_text("seq_name\tlength\ttopology\tplasmid_score\ncontig_1\t50000\tCircular\t0.95\n")
    run("amr_linkage.py", "--sample", "P1", "--amr", d / "amr.tsv", "--assembly_info", d / "asm.txt",
        "--plasmid_summary", d / "pl.tsv", "--out", d / "P1.amr_linked.tsv", "--out_mags", d / "P1.mags.tsv")
    am = list(csv.DictReader(open(d / "P1.amr_linked.tsv"), delimiter="\t"))
    assert len(am) == 1 and am[0]["confidence"] == "very_high" and am[0]["on_plasmid"] == "True"

    (d / "ann.tsv").write_text("##header\n#query\tseed_ortholog\tKEGG_ko\tKEGG_Module\tCAZy\ncontig_1_1\tx\tko:K00929\tM00001\tGH5\n")
    (d / "targets.tsv").write_text("function\tgene\tko\nbutyrate\tbuk\tK00929\n")
    run("function_summary.py", "--sample", "P1", "--annotations", d / "ann.tsv", "--assembly_info", d / "asm.txt",
        "--targets", d / "targets.tsv", "--outdir", d)
    ft = list(csv.DictReader(open(d / "P1.function_targets.tsv"), delimiter="\t"))
    assert ft[0]["detected"] == "True"

    run("build_report.py", "--version", "test", cwd=d)
    assert (d / "wf-gut-report.html").stat().st_size > 5000 and (d / "P1.sample_report.html").exists()
