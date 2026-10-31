#!/usr/bin/env nextflow
// Public test input for real-data runs on AWS: the first ~3 Gb of an ONT run, as one barcode folder plus a
// one-row sample sheet.
//   --dataset fecal (default): ZymoBIOMICS Fecal Reference D6323, EPI2ME zymo_fecal_2025.05, flow cell PAU85136,
//     R10.4.1, Dorado SUP 5.0.0 (the model medaka_model expects). Read from the unaligned BAM in ONT's open-data
//     bucket (eu-west-1), so only the start of the 221 GiB file is transferred.
//   --dataset mock: ZymoBIOMICS mock community run ERR2906227 (R9.4.1 GridION), from NCBI's SRA bucket on AWS.
//     ENA served the same run at 11-300 KB/s on 2026-10-31.
//   PANBIOME_REMOTE=1 PANBIOME_SCRIPT=infra/aws/fetch_test_reads.nf infra/aws/run.sh fetch-zymo-fecal --reads_dir s3://BUCKET/test_data/zymo_fecal
nextflow.enable.dsl = 2

params.reads_dir = null
params.dataset = 'fecal'
params.max_bases = 3000000000
params.container_sra = 'quay.io/biocontainers/sra-tools:3.2.1--h4304569_1'
params.aws_cli = '/opt/aws-cli/bin/aws'  // aws.batch.cliPath, mounted into every task container

// FASTQ on stdin -> OUT (gzipped), stopping after the first complete record that reaches MAX bases.
// Fails if the input ends first.
def headFastq(String out) {
    """awk -v max=${params.max_bases} -v out=${out} '
        { print | ("gzip -c > " out) }
        NR % 4 == 2 { bases += length(\$0) }
        NR % 4 == 0 { reads++; if (bases >= max) exit }
        END { close("gzip -c > " out); print "fetch: " reads " reads, " bases " bases" > "/dev/stderr"; if (bases < max) exit 1 }'"""
}

process ZYMO_FECAL_D6323 {
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
    ${params.aws_cli} s3 cp --no-sign-request --region eu-west-1 --only-show-errors \\
        s3://ont-open-data/zymo_fecal_2025.05/basecalls/PAU85136/basecalls.sup_5.0.0.4mC5mC6mA.bam - \\
        | samtools fastq - | ${headFastq('fastq_pass/barcode01/PAU85136_head.fastq.gz')}
    printf 'barcode,alias,type,group\\nbarcode01,ZYMO_FECAL,test_sample,fecal_reference\\n' > sample_sheet.csv
    """
}

process ZYMO_ERR2906227 {
    container params.container_sra
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
    ${params.aws_cli} s3 cp --no-sign-request --region us-east-1 --only-show-errors \\
        s3://sra-pub-run-odp/sra/ERR2906227/ERR2906227 ERR2906227.sra
    fastq-dump --stdout -F ./ERR2906227.sra | ${headFastq('fastq_pass/barcode01/ERR2906227_head.fastq.gz')}
    rm ERR2906227.sra
    printf 'barcode,alias,type,group\\nbarcode01,ZYMO,test_sample,mock\\n' > sample_sheet.csv
    """
}

workflow {
    if (!params.reads_dir) error "Set --reads_dir, for example s3://BUCKET/test_data/zymo_fecal"
    if (params.dataset == 'fecal') ZYMO_FECAL_D6323()
    else if (params.dataset == 'mock') ZYMO_ERR2906227()
    else error "--dataset must be fecal or mock"
}
