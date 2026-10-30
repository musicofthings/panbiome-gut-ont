#!/usr/bin/env nextflow
// Download the databases that fit on a normal instance straight into S3. Sources and sizes: docs/DATABASES.md.
// Kraken2 GTDB v226 and GTDB-Tk R232 are not fetched here.
//   PANBIOME_SCRIPT=infra/aws/fetch_dbs.nf infra/aws/run.sh fetch-dbs --db_dir s3://BUCKET/db
nextflow.enable.dsl = 2


params.db_dir   = null

process SYLPH_R226 {
    container params.container_core
    cpus 2; memory '4 GB'; errorStrategy 'retry'; maxRetries 2
    publishDir "${params.db_dir}/sylph", mode: 'copy'
    input: path map_script
    output: path 'gtdb-r226-c200-dbv2.syl2db'; path 'gtdb_r226_map.tsv'
    script:
    """
    fetch_url 'http://faust.compbio.cs.cmu.edu/sylph-stuff/gtdb-r226-c200-dbv2.syl2db' 'gtdb-r226-c200-dbv2.syl2db'
    fetch_url 'https://data.gtdb.ecogenomic.org/releases/release226/226.0/bac120_taxonomy_r226.tsv.gz' 'bac120_taxonomy_r226.tsv.gz'
    fetch_url 'https://data.gtdb.ecogenomic.org/releases/release226/226.0/ar53_taxonomy_r226.tsv.gz' 'ar53_taxonomy_r226.tsv.gz'
    gunzip bac120_taxonomy_r226.tsv.gz ar53_taxonomy_r226.tsv.gz
    python3 ${map_script} bac120_taxonomy_r226.tsv ar53_taxonomy_r226.tsv > gtdb_r226_map.tsv
    """
}

process CHECKM2 {
    container params.container_core
    cpus 2; memory '4 GB'; errorStrategy 'retry'; maxRetries 2
    publishDir "${params.db_dir}/checkm2", mode: 'copy'
    output: path 'CheckM2_database'
    script:
    """
    fetch_url 'https://zenodo.org/records/14897628/files/checkm2_database.tar.gz?download=1' 'db.tar.gz'
    tar xzf db.tar.gz && rm db.tar.gz
    """
}

process GENOMAD {
    container params.container_core
    cpus 2; memory '4 GB'; errorStrategy 'retry'; maxRetries 2
    publishDir "${params.db_dir}/genomad", mode: 'copy'
    output: path 'genomad_db'
    script:
    """
    fetch_url 'https://portal.nersc.gov/genomad/__data__/genomad_db_v1.9.tar.gz' 'db.tar.gz'
    tar xzf db.tar.gz && rm db.tar.gz
    """
}

process AMRFINDER {
    container params.container_amrfinder
    cpus 2; memory '4 GB'; errorStrategy 'retry'; maxRetries 2
    publishDir "${params.db_dir}", mode: 'copy'
    output: path 'amrfinder'
    script:
    """
    amrfinder_update --database amrfinder
    """
}

process EGGNOG_502 {
    container params.container_core
    cpus 4; memory '8 GB'; errorStrategy 'retry'; maxRetries 2
    publishDir "${params.db_dir}", mode: 'copy'
    output: path 'eggnog'
    script:
    """
    mkdir eggnog && cd eggnog
    fetch_url 'https://eggnog5.embl.de/download/emapperdb-5.0.2/eggnog.db.gz' 'eggnog.db.gz'
    fetch_url 'https://eggnog5.embl.de/download/emapperdb-5.0.2/eggnog.taxa.tar.gz' 'eggnog.taxa.tar.gz'
    fetch_url 'https://eggnog5.embl.de/download/emapperdb-5.0.2/eggnog_proteins.dmnd.gz' 'eggnog_proteins.dmnd.gz'
    gunzip eggnog.db.gz eggnog_proteins.dmnd.gz
    tar xzf eggnog.taxa.tar.gz && rm eggnog.taxa.tar.gz
    """
}

process HOST_CHM13 {
    container params.container_core
    cpus 8; memory '32 GB'; errorStrategy 'retry'; maxRetries 2
    publishDir "${params.db_dir}/host", mode: 'copy'
    output: path 'chm13v2.0.map-ont.mmi'
    script:
    """
    fetch_url 'https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/009/914/755/GCA_009914755.4_T2T-CHM13v2.0/GCA_009914755.4_T2T-CHM13v2.0_genomic.fna.gz' 'chm13v2.0.fna.gz'
    minimap2 -t ${task.cpus} -x map-ont -d chm13v2.0.map-ont.mmi chm13v2.0.fna.gz
    """
}

workflow {
    if (!params.db_dir) error "Set --db_dir, for example s3://BUCKET/db"
    SYLPH_R226(file("${projectDir}/../../bin/make_sylph_lineage_map.py"))
    CHECKM2()
    GENOMAD()
    AMRFINDER()
    EGGNOG_502()
    HOST_CHM13()
}
