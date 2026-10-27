process KRAKEN2 {
    tag "$meta.id"
    label 'big'
    container params.container_kraken2
    publishDir { "${params.out_dir}/samples/${meta.id}/taxonomy" }, mode: 'copy', pattern: '*.kreport'
    publishDir { "${params.out_dir}/samples/${meta.id}/taxonomy" }, mode: 'copy', pattern: '*.kraken2.out.gz', enabled: params.save_read_classification

    input:
    tuple val(meta), path(reads)
    path db

    output:
    tuple val(meta), path("${meta.id}.kreport"), emit: report
    path "${meta.id}.KRAKEN2.versions.txt", emit: versions
    path "${meta.id}.kraken2.out.gz", optional: true

    script:
    def mm = params.kraken2_memory_mapping ? '--memory-mapping' : ''
    """
    kraken2 --db ${db} --threads ${task.cpus} --confidence ${params.kraken2_confidence} ${mm} \\
        --report ${meta.id}.kreport ${reads} | gzip -c > ${meta.id}.kraken2.out.gz
    echo "kraken2 \$(kraken2 --version | head -1)" > ${meta.id}.KRAKEN2.versions.txt
    """

    stub:
    """
    printf ' 100.00\\t1000\\t0\\tR\\t1\\troot\\n' > ${meta.id}.kreport
    echo "" | gzip -c > ${meta.id}.kraken2.out.gz
    echo "kraken2 stub" > ${meta.id}.KRAKEN2.versions.txt
    """
}

process BRACKEN {
    tag "$meta.id"
    label 'small'
    container params.container_bracken
    publishDir { "${params.out_dir}/samples/${meta.id}/taxonomy" }, mode: 'copy'

    input:
    tuple val(meta), path(kreport)
    path db

    output:
    tuple val(meta), path("${meta.id}.bracken"), emit: bracken
    path "${meta.id}.BRACKEN.versions.txt", emit: versions

    script:
    """
    bracken -d ${db} -i ${kreport} -o ${meta.id}.bracken -w ${meta.id}.bracken.kreport \\
        -r ${params.bracken_read_len} -l S -t ${params.bracken_threshold}
    echo "bracken \$(bracken -v 2>&1 | head -1)" > ${meta.id}.BRACKEN.versions.txt
    """

    stub:
    """
    printf 'name\\ttaxonomy_id\\ttaxonomy_lvl\\tkraken_assigned_reads\\tadded_reads\\tnew_est_reads\\tfraction_total_reads\\n' > ${meta.id}.bracken
    echo "bracken stub" > ${meta.id}.BRACKEN.versions.txt
    """
}

process PARSE_KRAKEN {
    tag "$meta.id"
    label 'small'
    container params.container_core

    input:
    tuple val(meta), path(kreport), path(bracken)

    output:
    tuple val(meta), path("${meta.id}.bracken_species.tsv"), emit: table
    tuple val(meta), path("${meta.id}.krona.txt"),           emit: krona

    script:
    """
    parse_profiles.py kraken --kreport ${kreport} --bracken ${bracken} \\
        --out ${meta.id}.bracken_species.tsv --krona ${meta.id}.krona.txt
    """

    stub:
    """
    printf 'taxon\\tlineage\\treads\\trel_abundance\\tmethod\\tani\\tcoverage\\n' > ${meta.id}.bracken_species.tsv
    : > ${meta.id}.krona.txt
    """
}

process KRONA {
    tag "$meta.id"
    label 'small'
    container params.container_krona
    publishDir { "${params.out_dir}/samples/${meta.id}/taxonomy" }, mode: 'copy'

    input:
    tuple val(meta), path(krona_txt)

    output:
    tuple val(meta), path("${meta.id}.krona.html"), emit: html

    script:
    """
    if [ -s ${krona_txt} ]; then
        ktImportText -o ${meta.id}.krona.html ${krona_txt}
    else
        echo "<html><body>No classified reads.</body></html>" > ${meta.id}.krona.html
    fi
    """

    stub:
    """
    echo "<html></html>" > ${meta.id}.krona.html
    """
}

process SYLPH {
    tag "$meta.id"
    label 'medium'
    container params.container_sylph
    publishDir { "${params.out_dir}/samples/${meta.id}/taxonomy" }, mode: 'copy'

    input:
    tuple val(meta), path(reads)
    path db

    output:
    tuple val(meta), path("${meta.id}.sylph.tsv"), emit: profile
    path "${meta.id}.SYLPH.versions.txt", emit: versions

    script:
    """
    sylph profile ${db} ${reads} -t ${task.cpus} ${params.sylph_args} -o ${meta.id}.sylph.tsv
    echo "sylph \$(sylph --version 2>&1 | head -1)" > ${meta.id}.SYLPH.versions.txt
    """

    stub:
    """
    printf 'Sample_file\\tGenome_file\\tTaxonomic_abundance\\tSequence_abundance\\tAdjusted_ANI\\tEff_cov\\n' > ${meta.id}.sylph.tsv
    echo "sylph stub" > ${meta.id}.SYLPH.versions.txt
    """
}

process PARSE_SYLPH {
    tag "$meta.id"
    label 'small'
    container params.container_core

    input:
    tuple val(meta), path(profile)
    path lineage_map

    output:
    tuple val(meta), path("${meta.id}.sylph_species.tsv"), emit: table

    script:
    def lm = lineage_map.name != 'NO_FILE' ? "--lineage_map ${lineage_map}" : ''
    """
    parse_profiles.py sylph --tsv ${profile} ${lm} --out ${meta.id}.sylph_species.tsv
    """

    stub:
    """
    printf 'taxon\\tlineage\\treads\\trel_abundance\\tmethod\\tani\\tcoverage\\n' > ${meta.id}.sylph_species.tsv
    """
}

process EMU {
    tag "$meta.id"
    label 'big'
    container params.container_emu
    publishDir { "${params.out_dir}/samples/${meta.id}/taxonomy" }, mode: 'copy'

    input:
    tuple val(meta), path(reads)
    path db

    output:
    tuple val(meta), path("${meta.id}.emu.tsv"), emit: profile
    path "${meta.id}.EMU.versions.txt", emit: versions

    script:
    """
    emu abundance ${reads} --db ${db} --type map-ont --threads ${task.cpus} \\
        --output-dir emu_out --output-basename ${meta.id} --keep-counts
    cp emu_out/${meta.id}_rel-abundance.tsv ${meta.id}.emu.tsv
    echo "emu \$(emu --version 2>&1 | head -1)" > ${meta.id}.EMU.versions.txt
    """

    stub:
    """
    printf 'tax_id\\tabundance\\tspecies\\n' > ${meta.id}.emu.tsv
    echo "emu stub" > ${meta.id}.EMU.versions.txt
    """
}

process PARSE_EMU {
    tag "$meta.id"
    label 'small'
    container params.container_core

    input:
    tuple val(meta), path(profile)

    output:
    tuple val(meta), path("${meta.id}.emu_species.tsv"), emit: table

    script:
    """
    parse_profiles.py emu --tsv ${profile} --out ${meta.id}.emu_species.tsv
    """

    stub:
    """
    printf 'taxon\\tlineage\\treads\\trel_abundance\\tmethod\\tani\\tcoverage\\n' > ${meta.id}.emu_species.tsv
    """
}

process RECONCILE {
    tag "$meta.id"
    label 'small'
    container params.container_core
    publishDir { "${params.out_dir}/samples/${meta.id}/taxonomy" }, mode: 'copy'

    input:
    tuple val(meta), path(bracken, stageAs: 'in_b/*'), path(sylph, stageAs: 'in_s/*'), path(emu, stageAs: 'in_e/*')
    path synonyms, stageAs: 'in_y/*'
    path watchlist, stageAs: 'in_w/*'

    output:
    tuple val(meta), path("${meta.id}.species.tsv"),   emit: species
    tuple val(meta), path("${meta.id}.watchlist.tsv"), emit: watchlist
    tuple val(meta), path("${meta.id}.taxa_summary.json"), emit: summary

    script:
    def b = bracken.name != 'NO_FILE' ? "--bracken ${bracken}" : ''
    def s = sylph.name   != 'NO_FILE' ? "--sylph ${sylph}"     : ''
    def e = emu.name     != 'NO_FILE' ? "--emu ${emu}"         : ''
    def y = synonyms.name != 'NO_FILE' ? "--synonyms ${synonyms}" : ''
    def w = watchlist.name != 'NO_FILE' ? "--watchlist ${watchlist}" : ''
    def primary = (emu.name != 'NO_FILE' && bracken.name == 'NO_FILE' && sylph.name == 'NO_FILE') ? 'emu' : params.primary_method
    """
    reconcile_taxa.py --sample ${meta.id} ${b} ${s} ${e} ${y} ${w} \\
        --rule ${params.taxa_rule} --primary ${primary} \\
        --min_reads ${params.min_species_reads} --min_ani ${params.min_ani} --min_cov ${params.min_cov} \\
        --out ${meta.id}.species.tsv --watch_out ${meta.id}.watchlist.tsv --json ${meta.id}.taxa_summary.json
    """

    stub:
    """
    printf 'taxon\\tlineage\\tevidence\\tn_methods\\tbracken_reads\\tbracken_rel\\tsylph_rel\\tsylph_ani\\tsylph_cov\\temu_rel\\tkept\\tfinal_reads\\tfinal_rel_abundance\\n' > ${meta.id}.species.tsv
    printf 'sample\\ttaxon\\trel_abundance\\tthreshold\\tflag\\tnote\\n' > ${meta.id}.watchlist.tsv
    echo '{}' > ${meta.id}.taxa_summary.json
    """
}
