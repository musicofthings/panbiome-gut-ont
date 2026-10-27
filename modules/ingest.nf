process VALIDATE_SAMPLESHEET {
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}/run", mode: 'copy'

    input:
    val found
    path sample_sheet

    output:
    path 'sample_sheet.validated.csv', emit: sheet
    path 'sample_sheet.warnings.txt',  emit: warnings

    script:
    def sheet = sample_sheet.name != 'NO_FILE' ? "--sample_sheet ${sample_sheet}" : ''
    """
    validate_samplesheet.py \\
        --found "${found}" ${sheet} \\
        --pgx_barcodes "${params.pgx_barcodes}" \\
        --required_fields "${params.required_metadata}" \\
        --out sample_sheet.validated.csv \\
        --warnings sample_sheet.warnings.txt
    """

    stub:
    """
    if [ "${sample_sheet.name}" != "NO_FILE" ]; then
        cp ${sample_sheet} sample_sheet.validated.csv
    else
        printf 'barcode,alias,type\\n' > sample_sheet.validated.csv
        for b in \$(echo "${found}" | tr ',' ' '); do printf '%s,%s,test_sample\\n' \$b \$b >> sample_sheet.validated.csv; done
    fi
    : > sample_sheet.warnings.txt
    """
}

process INGEST {
    tag "$meta.id"
    label 'small'
    container params.container_core

    input:
    tuple val(meta), path(files, stageAs: 'input/*')

    output:
    tuple val(meta), path("${meta.id}.raw.fastq.gz"), path("${meta.id}.header.txt"), emit: reads

    script:
    """
    : > ${meta.id}.header.txt
    for f in input/*; do
        case "\$f" in
            *.bam)
                samtools view -H "\$f" | grep '^@RG' >> ${meta.id}.header.txt || true
                samtools fastq -@ ${task.cpus} -F 0x900 "\$f" ;;
            *.gz) zcat "\$f" ;;
            *)    cat "\$f" ;;
        esac
    done | gzip -c > ${meta.id}.raw.fastq.gz
    """

    stub:
    """
    : > ${meta.id}.header.txt
    echo "" | gzip -c > ${meta.id}.raw.fastq.gz
    """
}
