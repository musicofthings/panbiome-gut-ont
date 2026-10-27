// Assembly, polishing, binning, MAG QC, AMR, plasmids, genes and function.
// Every step tolerates an empty assembly (too little coverage) so profiling
// results are still delivered for that sample.

process FLYE {
    tag "$meta.id"
    label 'big'
    container params.container_flye
    publishDir "${params.out_dir}/samples/${meta.id}/assembly", mode: 'copy', pattern: '*.assembly_info.txt'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("${meta.id}.flye.fasta"), path("${meta.id}.assembly_info.txt"), emit: asm
    path "${meta.id}.FLYE.versions.txt", emit: versions

    script:
    """
    set +e
    flye --nano-hq ${reads} --meta --threads ${task.cpus} --out-dir flye_out ${params.flye_args}
    rc=\$?
    set -e
    if [ \$rc -ne 0 ] || [ ! -s flye_out/assembly.fasta ]; then
        echo "Flye produced no assembly for ${meta.id} (exit \$rc); continuing without assembly outputs" >&2
        mkdir -p flye_out
        : > flye_out/assembly.fasta
        printf '#seq_name\\tlength\\tcov.\\tcirc.\\trepeat\\tmult.\\talt_group\\tgraph_path\\n' > flye_out/assembly_info.txt
    fi
    cp flye_out/assembly.fasta ${meta.id}.flye.fasta
    cp flye_out/assembly_info.txt ${meta.id}.assembly_info.txt
    echo "flye \$(flye --version)" > ${meta.id}.FLYE.versions.txt
    """

    stub:
    """
    echo ">contig_1" > ${meta.id}.flye.fasta; echo "ACGTACGTACGT" >> ${meta.id}.flye.fasta
    printf '#seq_name\\tlength\\tcov.\\tcirc.\\trepeat\\tmult.\\talt_group\\tgraph_path\\ncontig_1\\t12\\t10\\tN\\tN\\t1\\t*\\t1\\n' > ${meta.id}.assembly_info.txt
    echo "flye stub" > ${meta.id}.FLYE.versions.txt
    """
}

process MEDAKA {
    tag "$meta.id"
    label 'big'
    container params.container_medaka

    input:
    tuple val(meta), path(reads), path(draft), path(info)

    output:
    tuple val(meta), path("${meta.id}.contigs.fasta"), path(info), emit: asm
    path "${meta.id}.MEDAKA.versions.txt", emit: versions

    script:
    """
    if [ -s ${draft} ]; then
        # Weights for this model name are not bundled, and the image model
        # stores are not writable by the container user. Download the file
        # Medaka's own URL template names, then pass that path to -m.
        model_path=\$(MEDAKA_MODEL_NAME="${params.medaka_model}" python -c 'import os, sys, pathlib, requests
import medaka.models as m
import medaka.options as o
name = os.environ["MEDAKA_MODEL_NAME"]
if os.path.isfile(name):
    print(os.path.abspath(name))
    raise SystemExit(0)
if name not in o.known_models:
    sys.exit("medaka model %s is not known to this image" % name)
limit = 1024 ** 3
last = None
for suffix in m.model_suffixes:
    fname = "%s%s" % (name, suffix)
    url = o.model_url_template.format(pkg=m.__package__, subdir=o.model_subdir, fname=fname)
    dest = pathlib.Path(fname)
    try:
        with requests.get(url, stream=True, timeout=120, allow_redirects=True) as r:
            r.raise_for_status()
            cl = r.headers.get("content-length")
            if cl is not None and int(cl) > limit:
                sys.exit("refusing model download: %s is %s bytes" % (url, cl))
            n = 0
            with dest.open("wb") as fh:
                for chunk in r.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    n += len(chunk)
                    if n > limit:
                        sys.exit("refusing model download: %s exceeded 1 GiB" % url)
                    fh.write(chunk)
        with m.open_model(str(dest)) as store:
            store.get_meta("model_function")
        print(dest.resolve())
        raise SystemExit(0)
    except Exception as e:
        last = e
        if dest.exists():
            dest.unlink()
sys.exit("could not download medaka model %s via the image URL template: %s" % (name, last))
')
        medaka_consensus -i ${reads} -d ${draft} -o medaka_out -t ${task.cpus} -m "\$model_path"
        cp medaka_out/consensus.fasta ${meta.id}.contigs.fasta
    else
        : > ${meta.id}.contigs.fasta
    fi
    echo "medaka \$(medaka --version 2>&1 | head -1)" > ${meta.id}.MEDAKA.versions.txt
    """

    stub:
    """
    cp ${draft} ${meta.id}.contigs.fasta
    echo "medaka stub" > ${meta.id}.MEDAKA.versions.txt
    """
}

process UNPOLISHED_CONTIGS {
    tag "$meta.id"
    label 'small'
    container params.container_core

    input:
    tuple val(meta), path(draft), path(info)

    output:
    tuple val(meta), path("${meta.id}.contigs.fasta"), path(info), emit: asm

    script:
    """
    cp ${draft} ${meta.id}.contigs.fasta
    """

    stub:
    """
    cp ${draft} ${meta.id}.contigs.fasta
    """
}

process MAP_CONTIGS {
    tag "$meta.id"
    label 'medium'
    container params.container_core
    publishDir "${params.out_dir}/samples/${meta.id}/assembly", mode: 'copy', pattern: '*.contig_depth.tsv'

    input:
    tuple val(meta), path(reads), path(contigs)

    output:
    tuple val(meta), path("${meta.id}.contigs.bam"), path("${meta.id}.contigs.bam.bai"), emit: bam
    tuple val(meta), path("${meta.id}.contig_depth.tsv"), emit: depth

    script:
    """
    if [ -s ${contigs} ]; then
        minimap2 -ax map-ont -t ${task.cpus} ${contigs} ${reads} | samtools sort -@ ${task.cpus} -o ${meta.id}.contigs.bam -
        samtools index ${meta.id}.contigs.bam
        samtools coverage ${meta.id}.contigs.bam > ${meta.id}.contig_depth.tsv
    else
        : > ${meta.id}.contigs.bam; : > ${meta.id}.contigs.bam.bai; : > ${meta.id}.contig_depth.tsv
    fi
    """

    stub:
    """
    : > ${meta.id}.contigs.bam; : > ${meta.id}.contigs.bam.bai; : > ${meta.id}.contig_depth.tsv
    """
}

process SEMIBIN2 {
    tag "$meta.id"
    label 'big'
    container params.container_semibin
    publishDir "${params.out_dir}/samples/${meta.id}/bins", mode: 'copy'

    input:
    tuple val(meta), path(contigs), path(bam), path(bai)

    output:
    tuple val(meta), path("${meta.id}_bins"), path("${meta.id}.contig_bins.tsv"), emit: bins
    path "${meta.id}.SEMIBIN2.versions.txt", emit: versions

    script:
    """
    mkdir -p ${meta.id}_bins
    printf 'contig\\tbin\\n' > ${meta.id}.contig_bins.tsv
    if [ -s ${contigs} ] && [ -s ${bam} ]; then
        SemiBin2 single_easy_bin -i ${contigs} -b ${bam} -o semibin_out \\
            --sequencing-type long_read --environment ${params.semibin_env} \\
            --threads ${task.cpus} --compression none || echo "SemiBin2 found no bins" >&2
        if ls semibin_out/output_bins/*.fa >/dev/null 2>&1; then
            for f in semibin_out/output_bins/*.fa; do
                b=\$(basename \$f .fa); cp \$f ${meta.id}_bins/${meta.id}_\$b.fa
                grep '^>' \$f | sed 's/^>//; s/ .*//' | awk -v b="${meta.id}_\$b" '{print \$1"\\t"b}' >> ${meta.id}.contig_bins.tsv
            done
        fi
    fi
    echo "semibin \$(SemiBin2 --version 2>&1 | head -1)" > ${meta.id}.SEMIBIN2.versions.txt
    """

    stub:
    """
    mkdir -p ${meta.id}_bins
    printf 'contig\\tbin\\n' > ${meta.id}.contig_bins.tsv
    echo "semibin stub" > ${meta.id}.SEMIBIN2.versions.txt
    """
}

process CHECKM2 {
    tag "$meta.id"
    label 'big'
    container params.container_checkm2
    publishDir "${params.out_dir}/samples/${meta.id}/bins", mode: 'copy'

    input:
    tuple val(meta), path(bins), path(contig_bins)
    path db

    output:
    tuple val(meta), path("${meta.id}.checkm2_quality.tsv"), emit: quality
    path "${meta.id}.CHECKM2.versions.txt", emit: versions

    script:
    """
    if ls ${bins}/*.fa >/dev/null 2>&1; then
        checkm2 predict --threads ${task.cpus} --input ${bins} --output-directory checkm2_out \\
            -x fa --database_path ${db} --force
        cp checkm2_out/quality_report.tsv ${meta.id}.checkm2_quality.tsv
    else
        printf 'Name\\tCompleteness\\tContamination\\n' > ${meta.id}.checkm2_quality.tsv
    fi
    echo "checkm2 \$(checkm2 --version 2>&1 | head -1)" > ${meta.id}.CHECKM2.versions.txt
    """

    stub:
    """
    printf 'Name\\tCompleteness\\tContamination\\n' > ${meta.id}.checkm2_quality.tsv
    echo "checkm2 stub" > ${meta.id}.CHECKM2.versions.txt
    """
}

process GTDBTK {
    tag "$meta.id"
    label 'big'
    container params.container_gtdbtk
    publishDir "${params.out_dir}/samples/${meta.id}/bins", mode: 'copy'

    input:
    tuple val(meta), path(bins), path(contig_bins)
    path db

    output:
    tuple val(meta), path("${meta.id}.gtdbtk.summary.tsv"), emit: summary
    path "${meta.id}.GTDBTK.versions.txt", emit: versions

    script:
    """
    export GTDBTK_DATA_PATH=\$(readlink -f ${db})
    printf 'user_genome\\tclassification\\n' > ${meta.id}.gtdbtk.summary.tsv
    if ls ${bins}/*.fa >/dev/null 2>&1; then
        gtdbtk classify_wf --genome_dir ${bins} --out_dir gtdbtk_out --extension fa \\
            --cpus ${task.cpus}
        for f in gtdbtk_out/gtdbtk.*.summary.tsv; do
            [ -e "\$f" ] && tail -n +2 "\$f" | cut -f1,2 >> ${meta.id}.gtdbtk.summary.tsv
        done
    fi
    echo "gtdbtk \$(gtdbtk --version 2>&1 | head -1)" > ${meta.id}.GTDBTK.versions.txt
    """

    stub:
    """
    printf 'user_genome\\tclassification\\n' > ${meta.id}.gtdbtk.summary.tsv
    echo "gtdbtk stub" > ${meta.id}.GTDBTK.versions.txt
    """
}

process AMRFINDER {
    tag "$meta.id"
    label 'medium'
    container params.container_amrfinder
    publishDir "${params.out_dir}/samples/${meta.id}/resistance", mode: 'copy'

    input:
    tuple val(meta), path(contigs), path(info)
    path db

    output:
    tuple val(meta), path("${meta.id}.amrfinder.tsv"), emit: amr
    path "${meta.id}.AMRFINDER.versions.txt", emit: versions

    script:
    def d = db.name != 'NO_FILE' ? "--database ${db}" : ''
    """
    if [ -s ${contigs} ]; then
        amrfinder --nucleotide ${contigs} --plus --threads ${task.cpus} ${d} -o ${meta.id}.amrfinder.tsv
    else
        : > ${meta.id}.amrfinder.tsv
    fi
    echo "amrfinderplus \$(amrfinder --version 2>&1 | head -1)" > ${meta.id}.AMRFINDER.versions.txt
    """

    stub:
    """
    : > ${meta.id}.amrfinder.tsv
    echo "amrfinder stub" > ${meta.id}.AMRFINDER.versions.txt
    """
}

process GENOMAD {
    tag "$meta.id"
    label 'big'
    container params.container_genomad
    publishDir "${params.out_dir}/samples/${meta.id}/resistance", mode: 'copy'

    input:
    tuple val(meta), path(contigs), path(info)
    path db

    output:
    tuple val(meta), path("${meta.id}.plasmid_summary.tsv"), emit: plasmids
    path "${meta.id}.GENOMAD.versions.txt", emit: versions

    script:
    """
    printf 'seq_name\\tlength\\ttopology\\tplasmid_score\\n' > ${meta.id}.plasmid_summary.tsv
    if [ -s ${contigs} ]; then
        genomad end-to-end --cleanup --threads ${task.cpus} ${contigs} genomad_out ${db}
        f=\$(find genomad_out -name '*_plasmid_summary.tsv' | head -1)
        [ -n "\$f" ] && cp "\$f" ${meta.id}.plasmid_summary.tsv
    fi
    echo "genomad \$(genomad --version 2>&1 | head -1)" > ${meta.id}.GENOMAD.versions.txt
    """

    stub:
    """
    printf 'seq_name\\tlength\\ttopology\\tplasmid_score\\n' > ${meta.id}.plasmid_summary.tsv
    echo "genomad stub" > ${meta.id}.GENOMAD.versions.txt
    """
}

process PYRODIGAL {
    tag "$meta.id"
    label 'medium'
    container params.container_pyrodigal

    input:
    tuple val(meta), path(contigs), path(info)

    output:
    tuple val(meta), path("${meta.id}.proteins.faa"), path(info), emit: proteins

    script:
    """
    if [ -s ${contigs} ]; then
        pyrodigal -i ${contigs} -p meta -a ${meta.id}.proteins.faa -f gff -o ${meta.id}.genes.gff -j ${task.cpus}
    else
        : > ${meta.id}.proteins.faa
    fi
    """

    stub:
    """
    : > ${meta.id}.proteins.faa
    """
}

process EGGNOG {
    tag "$meta.id"
    label 'big'
    container params.container_eggnog

    input:
    tuple val(meta), path(proteins), path(info)
    path db

    output:
    tuple val(meta), path("${meta.id}.emapper.annotations"), path(info), emit: annotations
    path "${meta.id}.EGGNOG.versions.txt", emit: versions

    script:
    """
    if [ -s ${proteins} ]; then
        emapper.py -i ${proteins} --itype proteins -o ${meta.id} --output_dir emapper_out \\
            --data_dir ${db} --cpu ${task.cpus} --override
        cp emapper_out/${meta.id}.emapper.annotations ${meta.id}.emapper.annotations
    else
        printf '#query\\tKEGG_ko\\n' > ${meta.id}.emapper.annotations
    fi
    echo "eggnog-mapper \$(emapper.py --version 2>&1 | head -1)" > ${meta.id}.EGGNOG.versions.txt
    """

    stub:
    """
    printf '#query\\tKEGG_ko\\n' > ${meta.id}.emapper.annotations
    echo "eggnog stub" > ${meta.id}.EGGNOG.versions.txt
    """
}

process FUNCTION_SUMMARY {
    tag "$meta.id"
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}/samples/${meta.id}/function", mode: 'copy'

    input:
    tuple val(meta), path(annotations), path(info)
    path targets

    output:
    tuple val(meta), path("${meta.id}.function_targets.tsv"), emit: targets
    path "${meta.id}.function_*.tsv"

    script:
    def t = targets.name != 'NO_FILE' ? "--targets ${targets}" : ''
    """
    function_summary.py --sample ${meta.id} --annotations ${annotations} --assembly_info ${info} ${t} --outdir .
    """

    stub:
    """
    for n in function_ko function_module function_cazy function_targets; do : > ${meta.id}.\$n.tsv; done
    """
}

process AMR_LINKAGE {
    tag "$meta.id"
    label 'small'
    container params.container_core
    publishDir "${params.out_dir}/samples/${meta.id}/resistance", mode: 'copy'

    input:
    tuple val(meta), path(amr), path(info), path(plasmids, stageAs: 'in_p/*'), path(contig_bins, stageAs: 'in_t/*'), path(bins, stageAs: 'in_d/*'), path(checkm, stageAs: 'in_c/*'), path(gtdb, stageAs: 'in_g/*')

    output:
    tuple val(meta), path("${meta.id}.amr_linked.tsv"), emit: amr
    tuple val(meta), path("${meta.id}.mags.tsv"),       emit: mags

    script:
    def pl = plasmids.name   != 'NO_FILE' ? "--plasmid_summary ${plasmids}" : ''
    def cb = contig_bins.name != 'NO_FILE' ? "--contig_bins ${contig_bins}" : ''
    def bd = bins.name       != 'NO_FILE' ? "--bins_dir ${bins}" : ''
    def ck = checkm.name     != 'NO_FILE' ? "--checkm ${checkm}" : ''
    def gt = gtdb.name       != 'NO_FILE' ? "--gtdbtk ${gtdb}" : ''
    """
    amr_linkage.py --sample ${meta.id} --amr ${amr} --assembly_info ${info} ${pl} ${cb} ${bd} ${ck} ${gt} \\
        --min_cov ${params.amr_min_cov} --min_id ${params.amr_min_id} \\
        --out ${meta.id}.amr_linked.tsv --out_mags ${meta.id}.mags.tsv
    """

    stub:
    """
    printf 'sample\\tgene\\n' > ${meta.id}.amr_linked.tsv
    printf 'sample\\tbin\\n' > ${meta.id}.mags.tsv
    """
}
