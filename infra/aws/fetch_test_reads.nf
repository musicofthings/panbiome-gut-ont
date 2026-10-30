#!/usr/bin/env nextflow
// Public test input for the first real-data run on AWS: the first ~3 Gb of ENA ERR2906227
// (ZymoBIOMICS mock community, ONT GridION), as one barcode folder plus a one-row sample sheet.
//   PANBIOME_REMOTE=1 PANBIOME_SCRIPT=infra/aws/fetch_test_reads.nf infra/aws/run.sh fetch-zymo --reads_dir s3://BUCKET/test_data/zymo
nextflow.enable.dsl = 2

params.reads_dir = null
params.max_bases = 3000000000

process ZYMO_ERR2906227 {
    container params.container_core
    cpus 2
    memory '4 GB'
    errorStrategy 'retry'
    maxRetries 2
    publishDir params.reads_dir, mode: 'copy'

    output:
    path 'fastq_pass'
    path 'sample_sheet.csv'

    script:
    """
    mkdir -p fastq_pass/barcode01
    head_fastq https://ftp.sra.ebi.ac.uk/vol1/fastq/ERR290/007/ERR2906227/ERR2906227.fastq.gz \\
        fastq_pass/barcode01/ERR2906227_head.fastq.gz ${params.max_bases}
    printf 'barcode,alias,type,group\\nbarcode01,ZYMO,test_sample,mock\\n' > sample_sheet.csv
    """
}

workflow {
    if (!params.reads_dir) error "Set --reads_dir, for example s3://BUCKET/test_data/zymo"
    ZYMO_ERR2906227()
}
