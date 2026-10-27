process CONTROL_STATUS {
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}/run/controls", mode: 'copy'

    input:
    path species
    path sheet
    path mock_expected, stageAs: 'in_m/*'
    path control_summary, stageAs: 'in_s/*'

    output:
    path 'control_status.json',               emit: status
    path 'control_summary.json',              emit: summary
    path 'control_contaminant_flags.tsv',     emit: flags

    script:
    def me = mock_expected.name   != 'NO_FILE' ? "--mock_expected ${mock_expected}"     : ''
    def cs = control_summary.name != 'NO_FILE' ? "--control_summary ${control_summary}" : ''
    """
    control_eval.py --sheet ${sheet} --species_dir . ${me} ${cs} \\
        --pipeline_version ${workflow.manifest.version} \\
        --max_age_days ${params.control_max_age_days} \\
        --mock_max_bray ${params.mock_max_bray} --mock_max_unexpected ${params.mock_max_unexpected} \\
        --out_status control_status.json --out_flags control_contaminant_flags.tsv \\
        --out_summary control_summary.json
    """

    stub:
    """
    echo '{"status":"MISSING","reason":"stub","release_patient_results":false}' > control_status.json
    echo '{}' > control_summary.json
    printf 'sample\\ttaxon\\n' > control_contaminant_flags.tsv
    """
}

process DIVERSITY {
    label 'medium'
    container params.container_core
    publishDir "${params.out_dir}/run", mode: 'copy'

    input:
    path species
    path sheet

    output:
    path 'diversity', emit: dir

    script:
    """
    diversity.py --sheet ${sheet} --species_dir . --group_col ${params.group_col} --outdir diversity
    """

    stub:
    """
    mkdir -p diversity; echo '{"n_samples":0}' > diversity/diversity_summary.json
    printf 'sample\\tobserved_species\\tshannon\\tsimpson\\tpielou_evenness\\tclassified_reads\\n' > diversity/alpha_diversity.tsv
    """
}

process BUILD_REPORT {
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}", mode: 'copy', pattern: 'wf-gut-report.html'
    publishDir "${params.out_dir}/samples", mode: 'copy', pattern: '*.sample_report.html',
        saveAs: { fn -> "${fn.replace('.sample_report.html', '')}/${fn}" }

    input:
    path inputs          // all upstream files, staged flat (build_report.py reads the cwd)
    path diversity
    path params_json

    output:
    path 'wf-gut-report.html',    emit: report
    path '*.sample_report.html',  emit: sample_reports

    script:
    """
    build_report.py --version ${workflow.manifest.version} --params_json ${params_json} \\
        --target_gb ${params.target_gb} --clinic "${params.clinic_name}"
    """

    stub:
    """
    echo "<html></html>" > wf-gut-report.html
    if [ -f sample_sheet.validated.csv ]; then
        tail -n +2 sample_sheet.validated.csv | while IFS=, read -r barcode alias rest; do
            [ -n "\$alias" ] || continue
            echo "<html></html>" > "\${alias}.sample_report.html"
        done
    else
        echo "<html></html>" > stub.sample_report.html
    fi
    """
}

process COLLECT_VERSIONS {
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}/execution", mode: 'copy'

    input:
    path versions

    output:
    path 'software_versions.txt'

    script:
    """
    cat *.versions.txt | sort -u > software_versions.txt
    """

    stub:
    """
    : > software_versions.txt
    """
}
