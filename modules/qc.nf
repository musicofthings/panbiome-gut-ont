process READ_STATS {
    tag "${meta.id}:${stage}"
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}/samples/${meta.id}/qc", mode: 'copy', pattern: '*.stats.json'

    input:
    tuple val(meta), path(fastq), path(header), val(stage)

    output:
    tuple val(meta), path("${meta.id}.${stage}.stats.json"), emit: stats

    script:
    def ad = params.adapters_fasta ? "--adapters_fasta ${params.adapters_fasta}" : ''
    """
    read_stats.py --fastq ${fastq} --sample ${meta.id} --stage ${stage} \\
        --bam_header ${header} ${ad} --json ${meta.id}.${stage}.stats.json
    """

    stub:
    """
    echo '{"sample":"${meta.id}","stage":"${stage}","reads":600000,"gb":3.5,"bases":3500000000,"n50":8000,"mean_q":18,"median_read_q":19,"basecall_tier":"sup","basecall_model":"stub","adapter_any_pct":0.1,"flow_cell_ids":["STUB"],"run_ids":["STUB"]}' > ${meta.id}.${stage}.stats.json
    """
}

process FILTER_READS {
    tag "$meta.id"
    label 'medium'
    container params.container_core

    input:
    tuple val(meta), path(fastq), path(header)

    output:
    tuple val(meta), path("${meta.id}.filtered.fastq.gz"), path(header), emit: reads
    path "${meta.id}.FILTER_READS.versions.txt", emit: versions

    script:
    def maxl = params.max_len ? "--maxlength ${params.max_len}" : ''
    """
    zcat ${fastq} | chopper --quality ${params.min_q} --minlength ${params.min_len} ${maxl} \\
        --threads ${task.cpus} | gzip -c > ${meta.id}.filtered.fastq.gz
    echo "chopper \$(chopper --version 2>&1 | head -1)" > ${meta.id}.FILTER_READS.versions.txt
    """

    stub:
    """
    echo "" | gzip -c > ${meta.id}.filtered.fastq.gz
    echo "chopper stub" > ${meta.id}.FILTER_READS.versions.txt
    """
}

// Human reads are counted and discarded here. Only non-host reads are written.
process HOST_DEPLETION {
    tag "$meta.id"
    label 'big'
    container params.container_core
    publishDir "${params.out_dir}/samples/${meta.id}/qc", mode: 'copy', pattern: '*.host.json'
    publishDir "${params.out_dir}/samples/${meta.id}/reads", mode: 'copy', pattern: '*.nonhost.fastq.gz', enabled: params.save_nonhost_reads

    input:
    tuple val(meta), path(fastq), path(header)
    path host_ref
    path pgx_bed

    output:
    tuple val(meta), path("${meta.id}.nonhost.fastq.gz"), emit: reads
    tuple val(meta), path("${meta.id}.host.json"),        emit: stats
    path "${meta.id}.HOST_DEPLETION.versions.txt",        emit: versions

    script:
    def bed = pgx_bed.name != 'NO_FILE' ? "--pgx_bed ${pgx_bed}" : ''
    """
    minimap2 -ax map-ont -t ${task.cpus} --secondary=no ${host_ref} ${fastq} \\
      | host_split.py --nonhost ${meta.id}.nonhost.fastq.gz --stats ${meta.id}.host.json \\
            --sample ${meta.id} --min_aligned_frac ${params.host_min_aligned_frac} ${bed}
    echo "minimap2 \$(minimap2 --version)" > ${meta.id}.HOST_DEPLETION.versions.txt
    """

    stub:
    """
    echo "" | gzip -c > ${meta.id}.nonhost.fastq.gz
    echo '{"sample":"${meta.id}","host_fraction":0.01,"nonhost_reads":590000,"pgx_carryover_reads":0,"pgx_carryover_flag":false}' > ${meta.id}.host.json
    echo "minimap2 stub" > ${meta.id}.HOST_DEPLETION.versions.txt
    """
}

process HOST_SKIP {
    tag "$meta.id"
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}/samples/${meta.id}/qc", mode: 'copy', pattern: '*.host.json'

    input:
    tuple val(meta), path(fastq), path(header)

    output:
    tuple val(meta), path("${meta.id}.nonhost.fastq.gz"), emit: reads
    tuple val(meta), path("${meta.id}.host.json"),        emit: stats

    script:
    """
    ln -s ${fastq} ${meta.id}.nonhost.fastq.gz
    echo '{"sample":"${meta.id}","host_depletion":"skipped","host_fraction":0,"nonhost_reads":0,"pgx_carryover_reads":0,"pgx_carryover_flag":false}' > ${meta.id}.host.json
    """

    stub:
    """
    ln -s ${fastq} ${meta.id}.nonhost.fastq.gz
    echo '{"sample":"${meta.id}","host_fraction":0}' > ${meta.id}.host.json
    """
}

process RUN_QC {
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}/run", mode: 'copy'

    input:
    path stats
    path sheet

    output:
    path 'qc_summary.tsv',  emit: tsv
    path 'qc_summary.json', emit: json

    script:
    """
    run_qc.py --stats_dir . --sheet ${sheet} \\
        --target_gb ${params.target_gb} --min_gb ${params.min_gb} --min_reads ${params.qc_min_reads} \\
        --min_mean_q ${params.qc_min_mean_q} --adapter_warn_pct ${params.adapter_warn_pct} \\
        --host_warn_pct ${params.host_warn_pct} --balance_ratio ${params.balance_ratio} \\
        --pore_count ${params.pore_count} --run_hours ${params.run_hours} \\
        --out_tsv qc_summary.tsv --out_json qc_summary.json
    """

    stub:
    """
    printf 'sample\\tstatus\\n' > qc_summary.tsv
    echo '{"samples":0}' > qc_summary.json
    """
}
