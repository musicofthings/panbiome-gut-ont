#!/usr/bin/env nextflow
// Build a size-capped Kraken2 + Bracken database from GTDB r226 representative genomes, with the same
// taxonomy and sequence IDs as the published Langmead k2_gtdb_genome_reps_20250609 build, so names still
// match the sylph r226 database. Runs on the panbiome-build queue (1000 GB disk).
//   PANBIOME_SCRIPT=infra/aws/build_kraken2.nf infra/aws/run.sh build-kraken2 --db_dir s3://BUCKET/db
nextflow.enable.dsl = 2

params.db_dir     = null
params.max_db_gb  = 64
params.read_len   = 1000

process KRAKEN2_GTDB_R226_CAPPED {
    container params.container_bracken
    queue 'panbiome-build'
    // r7i.4xlarge: with the head jobs this stays inside the account's 32 on-demand vCPU quota
    cpus 16
    memory '120 GB'
    publishDir params.db_dir, mode: 'copy'

    output:
    path "k2_gtdb_r226_${params.max_db_gb}GB"

    script:
    def db = "k2_gtdb_r226_${params.max_db_gb}GB"
    def max_bytes = (params.max_db_gb as long) * 1024L * 1024L * 1024L
    def k2 = 'https://genome-idx.s3.amazonaws.com/kraken/gtdb_genome_reps_20250609'
    def gtdb = 'https://data.gtdb.ecogenomic.org/releases/release226/226.0/genomic_files_reps/gtdb_genomes_reps_r226.tar.gz'
    """
    set -euo pipefail
    mkdir -p ${db}/taxonomy ${db}/library

    fetch_url ${k2}/names.dmp ${db}/taxonomy/names.dmp
    fetch_url ${k2}/nodes.dmp ${db}/taxonomy/nodes.dmp
    fetch_url ${k2}/seqid2taxid.map ${db}/seqid2taxid.map
    # Saved first (137 GB) so a dropped connection resumes instead of failing the stream.
    fetch_url ${gtdb} gtdb_genomes_reps_r226.tar.gz

    # Headers become kraken:taxid|TAXID|ACCESSION, as in the published build; sequences missing from its map are dropped.
    tar xzOf gtdb_genomes_reps_r226.tar.gz --wildcards '*.fna.gz' \\
      | gzip -dc \\
      | awk 'NR == FNR { split(\$1, f, "|"); id[f[3]] = \$1; next }
             /^>/ { acc = substr(\$1, 2); keep = (acc in id); if (keep) print ">" id[acc] substr(\$0, length(\$1) + 1); next }
             keep' ${db}/seqid2taxid.map - > ${db}/library/library.fna
    rm gtdb_genomes_reps_r226.tar.gz

    kraken2-build --build --db ${db} --threads ${task.cpus} --max-db-size ${max_bytes}
    bracken-build -d ${db} -t ${task.cpus} -k 35 -l ${params.read_len}

    rm -rf ${db}/library ${db}/database.kraken ${db}/database${params.read_len}mers.kraken
    kraken2-inspect --db ${db} --skip-counts | head -20
    """
}

workflow {
    if (!params.db_dir) error "Set --db_dir, for example s3://BUCKET/db"
    KRAKEN2_GTDB_R226_CAPPED()
}
