#!/usr/bin/env nextflow
// Classify one read file against a Kraken2 database at several --confidence values, to tell a database
// problem from a threshold problem. Writes kraken2-inspect's header and one report per value to --out_dir.
//   PANBIOME_REMOTE=1 PANBIOME_SCRIPT=infra/aws/kraken2_check.nf infra/aws/run.sh kraken2-check \
//     --reads s3://BUCKET/test_data/zymo/nonhost/ZYMO.nonhost.fastq.gz --kraken2_db s3://BUCKET/db/k2_gtdb_r226_64GB
nextflow.enable.dsl = 2

params.reads = null
params.kraken2_db = null
params.confidences = '0,0.05'

process KRAKEN2_CHECK {
    container params.container_kraken2
    cpus 8
    memory '80 GB'
    publishDir params.out_dir, mode: 'copy'

    input:
    path reads
    path db

    output:
    path 'inspect.txt'
    path 'conf_*.kreport'
    path 'summary.txt'

    script:
    """
    kraken2-inspect --db ${db} --skip-counts | head -12 > inspect.txt
    for c in ${params.confidences.tokenize(',').join(' ')}; do
        kraken2 --db ${db} --threads ${task.cpus} --confidence \$c --report conf_\$c.kreport ${reads} > /dev/null 2> conf_\$c.log
        echo "confidence \$c: \$(grep -E 'classified' conf_\$c.log | tr '\\n' ' ')" >> summary.txt
    done
    """
}

workflow {
    if (!params.reads || !params.kraken2_db) error "Set --reads and --kraken2_db"
    KRAKEN2_CHECK(file(params.reads), file(params.kraken2_db, type: 'dir'))
}
