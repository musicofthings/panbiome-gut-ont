#!/usr/bin/env python3
"""Generate nextflow_schema.json (EPI2ME renders its GUI from this file).

Run from the repo root:  python3 scripts/make_schema.py
tests/test_schema.py checks that every params.* key in nextflow.config
has an entry here.
"""
import json

S, I, N, B = "string", "integer", "number", "boolean"


def p(type_, desc, default=None, fmt=None, enum=None, help_=None, hidden=False, icon=None, minimum=None):
    d = {"type": type_, "description": desc}
    if default is not None:
        d["default"] = default
    if fmt:
        d["format"] = fmt
    if enum:
        d["enum"] = enum
    if help_:
        d["help_text"] = help_
    if hidden:
        d["hidden"] = True
    if icon:
        d["fa_icon"] = icon
    if minimum is not None:
        d["minimum"] = minimum
    return d


groups = {
    "input_options": ("Input options", "fas fa-terminal", "Sequencing data, sample sheet and assay.", {
        "fastq": p(S, "Basecalled reads: a folder of barcode folders (for example fastq_pass), a folder of FASTQ/BAM files, or one file.",
                   fmt="path", help_="Barcode folder names must match the 'barcode' column of the sample sheet. Unmapped BAM from Dorado is accepted; mapped BAM is not.",
                   icon="fas fa-file"),
        "sample_sheet": p(S, "CSV with columns barcode, alias, type and optional metadata.", fmt="file-path",
                          help_="type is one of test_sample, positive_control, negative_control, no_template_control. Extra columns such as group, subject_id, collection_date are carried into reports.",
                          icon="fas fa-table"),
        "out_dir": p(S, "Output folder.", default="output", fmt="directory-path", icon="fas fa-folder-open"),
        "assay": p(S, "Assay type.", default="shotgun", enum=["shotgun", "16s", "both"],
                   help_="shotgun = whole-genome metagenome. 16s = full-length 16S amplicons profiled with Emu."),
        "required_metadata": p(S, "Comma-separated sample sheet columns that must be filled for every sample.", default="",
                               help_="For example: subject_id,collection_date,extraction_lot,bristol_score,time_to_freezing_h"),
    }),
    "run_metadata": ("Flow cell and library", "fas fa-microchip", "Details about this flow cell use (washed, second library).", {
        "pgx_barcodes": p(S, "Barcodes used by the earlier PGx library on this flow cell.", default="",
                          help_="Any sample sheet barcode listed here is rejected, which prevents carryover from being mistaken for a gut sample."),
        "pgx_regions": p(S, "BED of PGx target regions in the host reference coordinates.", fmt="file-path",
                         help_="Human reads falling in these regions are counted as likely carryover from the PGx library and flagged."),
        "pore_count": p(I, "Available pores at the first pore scan.", default=0, minimum=0,
                        help_="Recorded in the report. A washed flow cell cannot repeat the Flow Cell Check, so use the pore scan value."),
        "run_hours": p(N, "Run time in hours.", default=0, minimum=0),
    }),
    "read_processing": ("Read filtering", "fas fa-filter", "Length and quality filters.", {
        "min_len": p(I, "Minimum read length (bp).", default=500, minimum=0),
        "max_len": p(I, "Maximum read length (bp). 0 means no limit.", default=0, minimum=0),
        "min_q": p(N, "Minimum mean read quality.", default=10, minimum=0),
        "adapters_fasta": p(S, "Extra adapter or barcode sequences for the residual-adapter check.", fmt="file-path"),
    }),
    "host_depletion": ("Host depletion", "fas fa-user-slash", "Human reads are counted and discarded; they are never written to disk.", {
        "host_ref": p(S, "Human reference as a minimap2 index (.mmi built with -x map-ont) or FASTA.", fmt="file-path",
                      help_="T2T-CHM13v2.0 is recommended. A prebuilt .mmi saves several minutes per sample."),
        "skip_host_depletion": p(B, "Skip host depletion (not recommended).", default=False,
                                 help_="Only for samples known to be free of human DNA."),
        "host_min_aligned_frac": p(N, "Fraction of a read that must align to the host to call it host.", default=0.5, minimum=0),
    }),
    "taxonomy": ("Species profiling", "fas fa-bacteria", "Databases and thresholds. All shotgun databases must share one taxonomy (GTDB recommended).", {
        "kraken2_db": p(S, "Kraken2 database folder (with Bracken files built for bracken_read_len).", fmt="directory-path"),
        "kraken2_confidence": p(N, "Kraken2 confidence threshold.", default=0.05, minimum=0),
        "kraken2_memory_mapping": p(B, "Memory-map the Kraken2 database instead of loading it into RAM.", default=False),
        "bracken_read_len": p(I, "Read length the Bracken kmer distribution was built for.", default=1000, minimum=1),
        "bracken_threshold": p(I, "Minimum reads for Bracken to re-estimate a species.", default=10, minimum=0),
        "sylph_db": p(S, "sylph database (.syldb).", fmt="file-path"),
        "sylph_lineage_map": p(S, "TSV mapping genome accession to GTDB lineage.", fmt="file-path",
                               help_="Build it with bin/make_sylph_lineage_map.py from the GTDB taxonomy files."),
        "sylph_args": p(S, "Extra arguments for sylph profile.", default="",
                        help_="For noisy long reads consider --read-seq-id; check `sylph profile --help` for your version and tune in the pilot."),
        "emu_db": p(S, "Emu database folder (for assay 16s or both).", fmt="directory-path"),
        "taxa_rule": p(S, "Species call rule when two shotgun methods run.", default="both", enum=["both", "either"],
                       help_="both keeps a species only when Kraken2/Bracken and sylph agree."),
        "primary_method": p(S, "Method that supplies final abundances.", default="bracken", enum=["bracken", "sylph", "emu"]),
        "min_species_reads": p(N, "Minimum Bracken reads to call a species.", default=50, minimum=0),
        "min_ani": p(N, "Minimum sylph adjusted ANI (%).", default=95, minimum=0),
        "min_cov": p(N, "Minimum sylph effective coverage.", default=0, minimum=0),
        "taxa_synonyms": p(S, "Optional TSV of name synonyms (alias then canonical name).", fmt="file-path"),
        "watchlist": p(S, "Gut watchlist TSV (taxon, min_rel_abundance, note).", fmt="file-path",
                       help_="Defaults to assets/gut_watchlist.tsv. Thresholds are placeholders until validated."),
        "save_read_classification": p(B, "Keep the per-read Kraken2 output.", default=False),
        "save_nonhost_reads": p(B, "Keep the non-host reads (human reads are never kept).", default=False),
    }),
    "assembly_annotation": ("Assembly and annotation", "fas fa-dna", "Long-read metagenome assembly, MAGs, resistance genes, plasmids and function.", {
        "skip_assembly": p(B, "Skip assembly and everything downstream of it.", default=False),
        "skip_polish": p(B, "Skip Medaka polishing.", default=False),
        "flye_args": p(S, "Extra arguments for Flye.", default=""),
        "medaka_model": p(S, "Medaka model matching the basecaller.", default="r1041_e82_400bps_sup_v5.0.0",
                          help_="Must match the flow cell chemistry and basecaller version; verify with `medaka tools list_models`."),
        "skip_binning": p(B, "Skip binning and MAG quality control.", default=False),
        "semibin_env": p(S, "SemiBin2 pretrained environment.", default="human_gut"),
        "checkm2_db": p(S, "CheckM2 diamond database (.dmnd).", fmt="file-path"),
        "gtdbtk_db": p(S, "GTDB-Tk reference data folder (optional, large).", fmt="directory-path"),
        "amrfinder_db": p(S, "AMRFinderPlus database folder.", fmt="directory-path"),
        "amr_min_cov": p(N, "Minimum % coverage of the reference gene to report.", default=90, minimum=0),
        "amr_min_id": p(N, "Minimum % identity to the reference gene to report.", default=90, minimum=0),
        "genomad_db": p(S, "geNomad database folder (enables plasmid calls).", fmt="directory-path"),
        "eggnog_db": p(S, "eggNOG-mapper data folder (enables functional profiling).", fmt="directory-path"),
        "functional_targets": p(S, "TSV of targeted gut functions (function, gene, ko).", fmt="file-path",
                                help_="Defaults to assets/functional_targets.tsv. The starter set must be curated before clinical use."),
    }),
    "controls_qc": ("Controls and QC", "fas fa-vial", "Scheduled-control handling and per-sample thresholds. All values are placeholders until validated.", {
        "mock_expected": p(S, "TSV of the mock community's expected composition (taxon, expected_rel_abundance).", fmt="file-path"),
        "control_summary": p(S, "control_summary.json from the latest scheduled control run.", fmt="file-path",
                             help_="Used when this run has no controls. Patient results are released only while it is PASS and fresh."),
        "control_max_age_days": p(I, "Maximum age of a referenced control run (days).", default=31, minimum=1),
        "mock_max_bray": p(N, "Maximum Bray-Curtis dissimilarity of the mock community.", default=0.30, minimum=0),
        "mock_max_unexpected": p(N, "Maximum abundance of taxa not in the mock community.", default=0.05, minimum=0),
        "target_gb": p(N, "Per-sample yield target after filtering (Gb); WARN below.", default=3.0, minimum=0),
        "min_gb": p(N, "Per-sample yield minimum (Gb); FAIL below.", default=1.0, minimum=0),
        "qc_min_reads": p(I, "Minimum reads after filtering; FAIL below.", default=100000, minimum=0),
        "qc_min_mean_q": p(N, "Minimum mean read quality; WARN below.", default=10, minimum=0),
        "adapter_warn_pct": p(N, "WARN when this % of reads still carry adapter.", default=5, minimum=0),
        "host_warn_pct": p(N, "WARN when this % of reads are human.", default=20, minimum=0),
        "balance_ratio": p(N, "WARN when a sample's yield is under this fraction of the run median.", default=0.5, minimum=0),
    }),
    "report_options": ("Report", "fas fa-file-medical", "Report labels and grouping.", {
        "clinic_name": p(S, "Name shown in report titles.", default="Panbiome"),
        "group_col": p(S, "Sample sheet column used to color plots and run PERMANOVA.", default="group"),
    }),
    "advanced_options": ("Advanced", "fas fa-cogs", "Resources and container images.", {
        "threads": p(I, "Threads for multi-threaded steps.", default=8, minimum=1),
        "big_memory": p(S, "Memory for the heaviest steps (databases, assembly).", default="32 GB"),
        "help": p(B, "Print help and exit.", default=False, hidden=True),
        "version": p(B, "Print version and exit.", default=False, hidden=True),
        **{("container_" + k): p(S, "Container image for %s." % k, hidden=True) for k in (
            "core", "kraken2", "bracken", "krona", "sylph", "emu", "flye", "medaka", "semibin",
            "checkm2", "gtdbtk", "amrfinder", "genomad", "pyrodigal", "eggnog")},
    }),
}

definitions = {}
for key, (title, icon, desc, props) in groups.items():
    definitions[key] = {"title": title, "type": "object", "fa_icon": icon, "description": desc,
                        "properties": props}
definitions["input_options"]["required"] = ["fastq"]

schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://raw.githubusercontent.com/musicofthings/panbiome-gut-ont/main/nextflow_schema.json",
    "title": "musicofthings/panbiome-gut-ont",
    "workflow_title": "Panbiome gut microbiome (ONT)",
    "description": "Oxford Nanopore gut microbiome workflow for human stool: QC, host depletion, species profiling, assembly, MAGs, resistance genes, function, diversity and reports.",
    "demo_url": "",
    "aws_demo_url": "",
    "url": "https://github.com/musicofthings/panbiome-gut-ont",
    "type": "object",
    "definitions": definitions,
    "allOf": [{"$ref": "#/definitions/%s" % k} for k in definitions],
}

with open("nextflow_schema.json", "w") as fh:
    json.dump(schema, fh, indent=2)
    fh.write("\n")
print("wrote nextflow_schema.json with %d parameters" % sum(len(g[3]) for g in groups.values()))
