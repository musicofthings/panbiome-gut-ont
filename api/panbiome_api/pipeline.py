"""The main.nf process graph, grouped into stages, and which processes a run's params switch on."""

STAGES = [
    ("input", "Input"),
    ("qc", "Read QC"),
    ("host", "Host removal"),
    ("taxonomy", "Taxonomy"),
    ("community", "Community"),
    ("assembly", "Assembly"),
    ("mags", "MAGs"),
    ("amr", "AMR and mobile elements"),
    ("function", "Function"),
    ("report", "Report"),
]

# (process, stage, label, description)
PROCESSES = [
    ("VALIDATE_SAMPLESHEET", "input", "Validate sample sheet", "Checks barcodes, aliases and sample types"),
    ("INGEST", "input", "Ingest reads", "Merges each barcode's FASTQ/BAM files"),
    ("RAW_STATS", "qc", "Raw read stats", "Read count, length and quality before filtering"),
    ("FILTER_READS", "qc", "Filter reads", "Length and quality filter, adapter trimming"),
    ("FILTERED_STATS", "qc", "Filtered read stats", "Read stats after filtering"),
    ("HOST_DEPLETION", "host", "Remove human reads", "minimap2 against T2T-CHM13"),
    ("HOST_SKIP", "host", "Host removal skipped", "Reads pass through unchanged"),
    ("RUN_QC", "host", "Run QC", "Yield and pass/fail per sample"),
    ("KRAKEN2", "taxonomy", "Kraken2", "Read classification, GTDB r226"),
    ("BRACKEN", "taxonomy", "Bracken", "Species abundance re-estimation"),
    ("PARSE_KRAKEN", "taxonomy", "Parse Kraken2", "Species table from Kraken2 + Bracken"),
    ("KRONA", "taxonomy", "Krona", "Interactive taxonomy chart"),
    ("SYLPH", "taxonomy", "sylph", "Containment-based species profiling"),
    ("PARSE_SYLPH", "taxonomy", "Parse sylph", "Species table with GTDB lineages"),
    ("EMU", "taxonomy", "Emu", "16S species profiling"),
    ("PARSE_EMU", "taxonomy", "Parse Emu", "16S species table"),
    ("RECONCILE", "taxonomy", "Reconcile species", "Merges profilers into one species call set"),
    ("CONTROL_STATUS", "community", "Control status", "Mock, blank and NTC checks"),
    ("DIVERSITY", "community", "Diversity", "Alpha and beta diversity"),
    ("FLYE", "assembly", "Flye", "Metagenome assembly"),
    ("MEDAKA", "assembly", "Medaka", "Contig polishing"),
    ("UNPOLISHED_CONTIGS", "assembly", "Unpolished contigs", "Polishing skipped"),
    ("MAP_CONTIGS", "mags", "Map reads to contigs", "Coverage for binning"),
    ("SEMIBIN2", "mags", "SemiBin2", "Binning into MAGs"),
    ("CHECKM2", "mags", "CheckM2", "MAG completeness and contamination"),
    ("GTDBTK", "mags", "GTDB-Tk", "MAG taxonomy"),
    ("AMRFINDER", "amr", "AMRFinderPlus", "Resistance genes on contigs"),
    ("GENOMAD", "amr", "geNomad", "Plasmids and viruses"),
    ("AMR_LINKAGE", "amr", "AMR linkage", "Links AMR genes to plasmids and MAGs"),
    ("PYRODIGAL", "function", "Pyrodigal", "Gene calling"),
    ("EGGNOG", "function", "eggNOG-mapper", "Functional annotation"),
    ("FUNCTION_SUMMARY", "function", "Function summary", "Targeted pathways and genes"),
    ("COLLECT_VERSIONS", "report", "Tool versions", "Software versions used"),
    ("BUILD_REPORT", "report", "Build report", "HTML reports per run and sample"),
]

EDGES = [
    ("VALIDATE_SAMPLESHEET", "INGEST"),
    ("INGEST", "RAW_STATS"),
    ("INGEST", "FILTER_READS"),
    ("FILTER_READS", "FILTERED_STATS"),
    ("FILTER_READS", "HOST_DEPLETION"),
    ("FILTER_READS", "HOST_SKIP"),
    ("RAW_STATS", "RUN_QC"),
    ("FILTERED_STATS", "RUN_QC"),
    ("HOST_DEPLETION", "RUN_QC"),
    ("HOST_SKIP", "RUN_QC"),
    ("HOST_DEPLETION", "KRAKEN2"),
    ("HOST_SKIP", "KRAKEN2"),
    ("HOST_DEPLETION", "SYLPH"),
    ("HOST_SKIP", "SYLPH"),
    ("HOST_DEPLETION", "EMU"),
    ("HOST_SKIP", "EMU"),
    ("KRAKEN2", "BRACKEN"),
    ("BRACKEN", "PARSE_KRAKEN"),
    ("PARSE_KRAKEN", "KRONA"),
    ("PARSE_KRAKEN", "RECONCILE"),
    ("SYLPH", "PARSE_SYLPH"),
    ("PARSE_SYLPH", "RECONCILE"),
    ("EMU", "PARSE_EMU"),
    ("PARSE_EMU", "RECONCILE"),
    ("RECONCILE", "CONTROL_STATUS"),
    ("RECONCILE", "DIVERSITY"),
    ("HOST_DEPLETION", "FLYE"),
    ("HOST_SKIP", "FLYE"),
    ("FLYE", "MEDAKA"),
    ("FLYE", "UNPOLISHED_CONTIGS"),
    ("MEDAKA", "MAP_CONTIGS"),
    ("UNPOLISHED_CONTIGS", "MAP_CONTIGS"),
    ("MAP_CONTIGS", "SEMIBIN2"),
    ("SEMIBIN2", "CHECKM2"),
    ("SEMIBIN2", "GTDBTK"),
    ("MEDAKA", "AMRFINDER"),
    ("UNPOLISHED_CONTIGS", "AMRFINDER"),
    ("MEDAKA", "GENOMAD"),
    ("UNPOLISHED_CONTIGS", "GENOMAD"),
    ("AMRFINDER", "AMR_LINKAGE"),
    ("GENOMAD", "AMR_LINKAGE"),
    ("SEMIBIN2", "AMR_LINKAGE"),
    ("CHECKM2", "AMR_LINKAGE"),
    ("GTDBTK", "AMR_LINKAGE"),
    ("MEDAKA", "PYRODIGAL"),
    ("UNPOLISHED_CONTIGS", "PYRODIGAL"),
    ("PYRODIGAL", "EGGNOG"),
    ("EGGNOG", "FUNCTION_SUMMARY"),
    ("RUN_QC", "BUILD_REPORT"),
    ("RECONCILE", "BUILD_REPORT"),
    ("CONTROL_STATUS", "BUILD_REPORT"),
    ("DIVERSITY", "BUILD_REPORT"),
    ("AMR_LINKAGE", "BUILD_REPORT"),
    ("FUNCTION_SUMMARY", "BUILD_REPORT"),
    ("COLLECT_VERSIONS", "BUILD_REPORT"),
]

PROCESS_NAMES = [p[0] for p in PROCESSES]


def enabled_processes(params: dict | None) -> set[str]:
    """Processes main.nf runs for these params. With no params yet, every process is assumed possible."""
    if params is None:
        return set(PROCESS_NAMES)
    assay = params.get("assay") or "shotgun"
    shotgun = assay in ("shotgun", "both")
    s16 = assay in ("16s", "both")
    skip_host = bool(params.get("skip_host_depletion"))
    assembly = shotgun and not params.get("skip_assembly")
    polish = assembly and not params.get("skip_polish")
    binning = assembly and not params.get("skip_binning")

    on = {
        "VALIDATE_SAMPLESHEET",
        "INGEST",
        "RAW_STATS",
        "FILTER_READS",
        "FILTERED_STATS",
        "RUN_QC",
        "RECONCILE",
        "CONTROL_STATUS",
        "DIVERSITY",
        "COLLECT_VERSIONS",
        "BUILD_REPORT",
    }
    on.add("HOST_SKIP" if skip_host else "HOST_DEPLETION")
    if shotgun and params.get("kraken2_db"):
        on |= {"KRAKEN2", "BRACKEN", "PARSE_KRAKEN", "KRONA"}
    if shotgun and params.get("sylph_db"):
        on |= {"SYLPH", "PARSE_SYLPH"}
    if s16:
        on |= {"EMU", "PARSE_EMU"}
    if assembly:
        on |= {"FLYE", "AMRFINDER", "AMR_LINKAGE", "MEDAKA" if polish else "UNPOLISHED_CONTIGS"}
        if params.get("genomad_db"):
            on.add("GENOMAD")
        if params.get("eggnog_db"):
            on |= {"PYRODIGAL", "EGGNOG", "FUNCTION_SUMMARY"}
    if binning:
        on |= {"MAP_CONTIGS", "SEMIBIN2"}
        if params.get("checkm2_db"):
            on.add("CHECKM2")
        if params.get("gtdbtk_db"):
            on.add("GTDBTK")
    return on


def graph() -> dict:
    return {
        "stages": [{"id": s, "label": label} for s, label in STAGES],
        "processes": [
            {"id": p, "stage": stage, "label": label, "description": desc} for p, stage, label, desc in PROCESSES
        ],
        "edges": [{"source": a, "target": b} for a, b in EDGES],
    }
