#!/usr/bin/env nextflow
/*
 * panbiome-gut-ont
 * Oxford Nanopore gut microbiome workflow (human stool), built for EPI2ME.
 */
nextflow.enable.dsl = 2

include { VALIDATE_SAMPLESHEET; INGEST } from './modules/ingest'
include { READ_STATS as RAW_STATS; READ_STATS as FILTERED_STATS;
          FILTER_READS; HOST_DEPLETION; HOST_SKIP; RUN_QC } from './modules/qc'
include { KRAKEN2; BRACKEN; PARSE_KRAKEN; KRONA; SYLPH; PARSE_SYLPH;
          EMU; PARSE_EMU; RECONCILE } from './modules/profiling'
include { FLYE; MEDAKA; UNPOLISHED_CONTIGS; MAP_CONTIGS; SEMIBIN2; CHECKM2; GTDBTK;
          AMRFINDER; GENOMAD; PYRODIGAL; EGGNOG; FUNCTION_SUMMARY; AMR_LINKAGE } from './modules/assembly'
include { CONTROL_STATUS; DIVERSITY; BUILD_REPORT; COLLECT_VERSIONS } from './modules/reporting'

// ---------------------------------------------------------------- helpers

def helpMessage() {
    log.info """
    panbiome-gut-ont v${workflow.manifest.version}

    nextflow run main.nf --fastq <fastq_pass|folder|file> --sample_sheet <csv> [options]

    Required
      --fastq            folder of barcode folders, folder of FASTQ/BAM files, or a single file
    Common
      --sample_sheet     CSV with columns barcode,alias,type (test_sample | positive_control |
                         negative_control | no_template_control) plus optional metadata columns
      --assay            shotgun (default) | 16s | both
      --out_dir          output folder (default: output)
      --host_ref         human reference (.mmi or FASTA) for host removal
      --kraken2_db / --sylph_db / --emu_db   classification databases
    Run -profile standard (docker) for a normal run. See docs/ and nextflow_schema.json.
    """.stripIndent()
}

def isReads(f) {
    return f.name ==~ /(?i).*\.(fastq|fq)(\.gz)?|.*\.bam/
}

// returns a list of [id, [files]]
def discoverInputs(String path) {
    def p = file(path, checkIfExists: true)
    def out = []
    if (p.isFile()) {
        out << [p.name.replaceFirst(/(?i)\.(fastq|fq|bam)(\.gz)?$/, ''), [p]]
    } else {
        def kids = p.listFiles()
        def direct = kids.findAll { it.isFile() && isReads(it) }.sort { it.name }
        if (direct) {
            out << [p.name, direct]
        }
        kids.findAll { it.isDirectory() }.sort { it.name }.each { d ->
            def fs = d.listFiles().findAll { it.isFile() && isReads(it) }.sort { it.name }
            if (fs) {
                out << [d.name, fs]
            }
        }
    }
    if (!out) {
        error "No FASTQ/BAM files found under ${path}"
    }
    return out
}

def noFile() {
    return file("${workflow.projectDir}/assets/NO_FILE")
}

def optFile(value) {
    return value ? file(value, checkIfExists: true) : noFile()
}

// left join on the first element, replacing missing items with the NO_FILE placeholder
def joinOpt(left, right) {
    def nf = noFile()
    return left.join(right, remainder: true).map { row -> row.collect { it == null ? nf : it } }
}

// ---------------------------------------------------------------- workflow

workflow {
    if (params.help) {
        helpMessage()
        System.exit(0)
    }
    if (params.version) {
        log.info "panbiome-gut-ont ${workflow.manifest.version}"
        System.exit(0)
    }
    if (!params.fastq) {
        error "Please provide --fastq"
    }
    if (!(params.assay in ['shotgun', '16s', 'both'])) {
        error "--assay must be shotgun, 16s or both"
    }
    if (!params.host_ref && !params.skip_host_depletion) {
        error "Provide --host_ref so human reads are removed, or set --skip_host_depletion true explicitly."
    }
    def shotgun = params.assay in ['shotgun', 'both']
    def s16 = params.assay in ['16s', 'both']
    if (shotgun && !params.kraken2_db && !params.sylph_db) {
        error "Shotgun profiling needs --kraken2_db and/or --sylph_db"
    }
    if (s16 && !params.emu_db) {
        error "16S profiling needs --emu_db"
    }

    // ---- inputs and sample sheet
    def discovered = discoverInputs(params.fastq)
    def found = discovered.collect { it[0] }.join(',')
    VALIDATE_SAMPLESHEET(found, optFile(params.sample_sheet))

    def sheet_rows = VALIDATE_SAMPLESHEET.out.sheet
        .splitCsv(header: true)
        .map { row -> [row.barcode, row] }

    def ch_reads = Channel.fromList(discovered)
        .map { id, files -> [id, files] }
        .join(sheet_rows)
        .map { bc, files, row -> [[id: row.alias] + row, files] }

    INGEST(ch_reads)

    // ---- read QC and filtering
    RAW_STATS(INGEST.out.reads.map { m, fq, h -> [m, fq, h, 'raw'] })
    FILTER_READS(INGEST.out.reads)
    FILTERED_STATS(FILTER_READS.out.reads.map { m, fq, h -> [m, fq, h, 'filtered'] })

    // ---- host depletion (human reads are discarded, never stored)
    def nonhost
    def host_stats
    def host_versions = Channel.empty()
    if (params.skip_host_depletion) {
        HOST_SKIP(FILTER_READS.out.reads)
        nonhost = HOST_SKIP.out.reads
        host_stats = HOST_SKIP.out.stats
    } else {
        HOST_DEPLETION(FILTER_READS.out.reads, file(params.host_ref, checkIfExists: true), optFile(params.pgx_regions))
        nonhost = HOST_DEPLETION.out.reads
        host_stats = HOST_DEPLETION.out.stats
        host_versions = HOST_DEPLETION.out.versions
    }

    def qc_in = RAW_STATS.out.stats.map { it[1] }
        .mix(FILTERED_STATS.out.stats.map { it[1] }, host_stats.map { it[1] })
        .collect()
    RUN_QC(qc_in, VALIDATE_SAMPLESHEET.out.sheet)

    // ---- species profiling
    // Controls and test samples are all profiled; only test samples are assembled.
    def tables_br = Channel.empty()
    def tables_sy = Channel.empty()
    def tables_em = Channel.empty()
    def tool_versions = FILTER_READS.out.versions.mix(host_versions)

    if (shotgun && params.kraken2_db) {
        KRAKEN2(nonhost, file(params.kraken2_db, checkIfExists: true))
        BRACKEN(KRAKEN2.out.report, file(params.kraken2_db, checkIfExists: true))
        PARSE_KRAKEN(KRAKEN2.out.report.join(BRACKEN.out.bracken))
        KRONA(PARSE_KRAKEN.out.krona)
        tables_br = PARSE_KRAKEN.out.table.map { m, f -> [m.id, f] }
        tool_versions = tool_versions.mix(KRAKEN2.out.versions, BRACKEN.out.versions)
    }
    if (shotgun && params.sylph_db) {
        SYLPH(nonhost, file(params.sylph_db, checkIfExists: true))
        PARSE_SYLPH(SYLPH.out.profile, optFile(params.sylph_lineage_map))
        tables_sy = PARSE_SYLPH.out.table.map { m, f -> [m.id, f] }
        tool_versions = tool_versions.mix(SYLPH.out.versions)
    }
    if (s16) {
        EMU(nonhost, file(params.emu_db, checkIfExists: true))
        PARSE_EMU(EMU.out.profile)
        tables_em = PARSE_EMU.out.table.map { m, f -> [m.id, f] }
        tool_versions = tool_versions.mix(EMU.out.versions)
    }

    def ch_meta = nonhost.map { m, fq -> [m.id, m] }
    def rec_in = joinOpt(joinOpt(joinOpt(ch_meta, tables_br), tables_sy), tables_em)
        .map { id, m, b, s, e -> [m, b, s, e] }
    RECONCILE(rec_in, optFile(params.taxa_synonyms), optFile(params.watchlist))

    // ---- controls and community statistics
    def species_files = RECONCILE.out.species.map { it[1] }.collect()
    CONTROL_STATUS(species_files, VALIDATE_SAMPLESHEET.out.sheet,
                   optFile(params.mock_expected), optFile(params.control_summary))
    DIVERSITY(species_files, VALIDATE_SAMPLESHEET.out.sheet)

    // ---- assembly, MAGs, AMR, function (test samples, shotgun only)
    def report_extra = Channel.empty()
    if (shotgun && !params.skip_assembly) {
        def test_reads = nonhost.filter { m, fq -> m.type == 'test_sample' }
        FLYE(test_reads)
        tool_versions = tool_versions.mix(FLYE.out.versions)

        def contigs
        if (params.skip_polish) {
            UNPOLISHED_CONTIGS(FLYE.out.asm)
            contigs = UNPOLISHED_CONTIGS.out.asm
        } else {
            MEDAKA(test_reads.map { m, fq -> [m.id, m, fq] }
                       .join(FLYE.out.asm.map { m, a, i -> [m.id, a, i] })
                       .map { id, m, fq, a, i -> [m, fq, a, i] })
            contigs = MEDAKA.out.asm
            tool_versions = tool_versions.mix(MEDAKA.out.versions)
        }

        // keyed copies for joins: [id, meta, contigs, info]
        def contigs_k = contigs.map { m, c, i -> [m.id, m, c, i] }

        AMRFINDER(contigs, optFile(params.amrfinder_db))
        tool_versions = tool_versions.mix(AMRFINDER.out.versions)

        def plasmid_ch = Channel.empty()
        if (params.genomad_db) {
            GENOMAD(contigs, file(params.genomad_db, checkIfExists: true))
            plasmid_ch = GENOMAD.out.plasmids.map { m, f -> [m.id, f] }
            tool_versions = tool_versions.mix(GENOMAD.out.versions)
        }

        def bins_ch = Channel.empty()
        def checkm_ch = Channel.empty()
        def gtdb_ch = Channel.empty()
        if (!params.skip_binning) {
            MAP_CONTIGS(test_reads.map { m, fq -> [m.id, m, fq] }
                            .join(contigs.map { m, c, i -> [m.id, c] })
                            .map { id, m, fq, c -> [m, fq, c] })
            SEMIBIN2(contigs.map { m, c, i -> [m.id, m, c] }
                         .join(MAP_CONTIGS.out.bam.map { m, b, bi -> [m.id, b, bi] })
                         .map { id, m, c, b, bi -> [m, c, b, bi] })
            bins_ch = SEMIBIN2.out.bins.map { m, d, t -> [m.id, d, t] }
            tool_versions = tool_versions.mix(SEMIBIN2.out.versions)
            if (params.checkm2_db) {
                CHECKM2(SEMIBIN2.out.bins, file(params.checkm2_db, checkIfExists: true))
                checkm_ch = CHECKM2.out.quality.map { m, f -> [m.id, f] }
                tool_versions = tool_versions.mix(CHECKM2.out.versions)
            }
            if (params.gtdbtk_db) {
                GTDBTK(SEMIBIN2.out.bins, file(params.gtdbtk_db, checkIfExists: true))
                gtdb_ch = GTDBTK.out.summary.map { m, f -> [m.id, f] }
                tool_versions = tool_versions.mix(GTDBTK.out.versions)
            }
        }

        // AMR linkage: [id, meta, amr, info, plasmids, contig_bins, bins_dir, checkm, gtdb]
        def amr_k = AMRFINDER.out.amr.map { m, a -> [m.id, m, a] }
            .join(contigs_k.map { id, m, c, i -> [id, i] })
        def link_in = joinOpt(amr_k, plasmid_ch)
        link_in = joinOpt(link_in, bins_ch.map { id, d, t -> [id, t, d] })
        link_in = joinOpt(link_in, checkm_ch)
        link_in = joinOpt(link_in, gtdb_ch)
        AMR_LINKAGE(link_in.map { id, m, a, i, p, t, d, c, g -> [m, a, i, p, t, d, c, g] })

        // function
        if (params.eggnog_db && !params.skip_assembly) {
            PYRODIGAL(contigs)
            EGGNOG(PYRODIGAL.out.proteins, file(params.eggnog_db, checkIfExists: true))
            FUNCTION_SUMMARY(EGGNOG.out.annotations, optFile(params.functional_targets))
            tool_versions = tool_versions.mix(EGGNOG.out.versions)
            report_extra = report_extra.mix(FUNCTION_SUMMARY.out.targets.map { it[1] })
        }
        report_extra = report_extra.mix(AMR_LINKAGE.out.amr.map { it[1] }, AMR_LINKAGE.out.mags.map { it[1] })
    }

    // ---- reports
    def pj = file("${params.out_dir}/execution/params.json")
    pj.parent.mkdirs()
    pj.text = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(params))

    COLLECT_VERSIONS(tool_versions.collect())

    def report_inputs = species_files.flatten()
        .mix(RECONCILE.out.watchlist.map { it[1] },
             RUN_QC.out.tsv, RUN_QC.out.json,
             VALIDATE_SAMPLESHEET.out.sheet, VALIDATE_SAMPLESHEET.out.warnings,
             CONTROL_STATUS.out.status, CONTROL_STATUS.out.flags,
             report_extra,
             tool_versions)
        .collect()
    BUILD_REPORT(report_inputs, DIVERSITY.out.dir, Channel.value(pj))
}

workflow.onComplete {
    log.info(workflow.success
        ? "\nDone. Open ${params.out_dir}/wf-gut-report.html"
        : "\nWorkflow failed: ${workflow.errorMessage}")
}
