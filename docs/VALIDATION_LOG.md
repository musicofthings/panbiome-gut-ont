# Validation log

Running record for panbiome-gut-ont. Each entry is a command that was actually run. Status is passed, failed, or not run.

## Unverified

Checked on 2026-10-27 against the pinned images. These items were not settled by `--help`:

- Emu 3.6.2 `--help` lists `names_df.tsv`, `nodes_df.tsv`, `species_taxid.fasta` and `unique_taxids.tsv`. The installed script reads `taxonomy.tsv` from `--db`. Which files a current prebuilt database contains was not checked.
- SemiBin2 2.6.0 `single_easy_bin` downloads GTDB (the help text says more than 100 GB) when `--reference-db` is unset and `~/.cache/SemiBin/mmseqs2-GTDB` is missing. The workflow does not pass `--reference-db`. Do not run binning until that path is supplied or the download is approved.
- eggNOG-mapper `--dmnd_db` is optional in the pinned 2.1.15 help, and the default download includes `eggnog_proteins.dmnd.gz` unless `-D` is set. `--data_dir` was not run against a real database. The image script's host `eggnogdb.embl.de` did not resolve. See the Phase 5 entry.
- `--bracken_read_len 1000` matches Bracken `-r`. Phase 4 built `database1000mers.kmer_distrib` in the tiny database with `bracken-build -l 1000`. A full database has not been built.
- Phase 4 ran real reads against that tiny database, then Flye and Medaka. See the Phase 4 entry. Full reference databases, binning, AMRFinder, geNomad and eggNOG were not run.

## 2026-10-27 — Phase 0: environment

| Check | Command | Result |
| --- | --- | --- |
| Python helpers and schema | `python3 -m pytest tests -q` | Passed. 8 passed in 16.40s. |
| Docker | `docker --version` | Passed. Docker version 29.7.2, build a7dcaa6. |
| Java | `java -version` | Passed. openjdk 17.0.20 (Homebrew). |
| Nextflow | `nextflow -version` | Passed. 23.10.0 build 5889. Meets `>=23.10.0`. Already on `PATH` at `/usr/local/bin/nextflow`. Not reinstalled. |

No `~/.nextflow/config`, so `-profile test` does not enable Docker. Nothing in the workflow was changed.

## 2026-10-27 — Phase 1: core image

Docker Desktop was not running at the start of this phase (`docker info` could not reach `unix:///Users/theranosis_dx/.docker/run/docker.sock`). Started it with `open -a Docker` and waited until `docker info` reported server 29.7.2.

| Check | Command | Result |
| --- | --- | --- |
| Build | `docker build -t ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0 -f docker/Dockerfile docker` | Passed. Image `e1dd5c49b4bc`, 2.04 GB. Not pushed. |
| Smoke | `docker run --rm ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0 bash -lc 'minimap2 --version; samtools --version \| head -1; chopper --version; python -c "import numpy, scipy, pandas, matplotlib; print(\"py ok\")"; ps --version'` | Passed. minimap2 2.30-r1287; samtools 1.24; chopper 0.14.1; `py ok`. `ps --version` printed `ps from procps-ng UNKNOWN` and exited 0. The binary is present; the package does not embed a version string. |

`bin/` was not copied into the image. The workflow adds the project `bin/` directory to `PATH`. Nothing in the workflow was changed.

Full build log: `/tmp/panbiome-docker-build.log`.

## 2026-10-27 — Phase 2: stub DAG

The runbook variant lines omit `--fastq`, `--sample_sheet` and `--host_ref`. Each variant below includes those, plus the database the branch requires. Work directories were `/tmp/panbiome-stub-<name>`, separate from the main `work/` directory. Nextflow 23.10.0. `-profile test` does not enable Docker. Every run printed `Task runtime metrics are not reported when using macOS without a container engine`.

| Check | Result |
| --- | --- |
| `bash tests/stub_run.sh` (first) | Passed, 54 tasks. `stub_output/wf-gut-report.html` and `stub_output/run/qc_summary.tsv` were present. Sample folders were `barcode01`, `barcode02`, `barcode03`, plus `samples/stub`. The blank was assembled. |
| Cause | The `VALIDATE_SAMPLESHEET` stub ignored the real sheet and wrote `alias` equal to the barcode, with every row `test_sample`. `BUILD_REPORT` stub wrote one `stub.sample_report.html`. |
| Fix | `modules/ingest.nf`: when a sample sheet is supplied, the stub copies it. `modules/reporting.nf`: the stub writes one `<alias>.sample_report.html` per sheet row. `test_data/make_test_data.py` now also writes `stub_db/emu/emu_stub.txt` and `control_summary.json`. |
| `bash tests/stub_run.sh` (after the fix) | Passed, 48 tasks. Folders: `samples/P001`, `samples/P002`, `samples/BLANK1`, each with a sample report. Assembly, bins and resistance exist only for P001 and P002 (2 of 2). BLANK1 has QC and taxonomy only. |
| `--assay 16s --emu_db test_data/stub_db/emu` | Passed. Emu ran. Kraken2 and Flye did not. No `assembly/` directories. |
| `--assay both` with Kraken2 and Emu databases | Passed. Kraken2, Emu and Flye all ran. Assembly dirs for P001 and P002. |
| `--skip_assembly` | Passed. No Flye process and no `assembly/` directories. |
| `--skip_host_depletion` | Passed. `HOST_SKIP` ran (3 of 3). `HOST_DEPLETION` did not. |
| `--control_summary test_data/control_summary.json` | Passed. The file is accepted. The stub does not read its contents. |

The channel-reuse errors predicted from reading `main.nf` did not occur on Nextflow 23.10.0. `species_files`, `tool_versions` and `test_reads` were each used by more than one operator, and the run still completed. No change was made to `main.nf`.

This does not validate tool command lines or real data.

## 2026-10-27 — Phase 3: tool flags

Each pinned tag was pulled with `docker pull` and the command in `modules/*.nf` was compared with that image's `--help`. Help text is in `/tmp/panbiome-help/`. Free disk after the pulls: 95 GB. No image was rejected by the registry.

| Tool | Image | Result |
| --- | --- | --- |
| chopper 0.14.1 | core image | Passed. `--quality`, `--minlength`, `--maxlength`, `--threads` are in `chopper --help`. |
| minimap2 2.30-r1287 | core image | Passed. `-a`, `-x map-ont` and `-t` are in `--help`. `--secondary=no` is not in the short help. A two-sequence run with `-ax map-ont --secondary=no` exited 0 and echoed the flag in the `@PG` line. |
| samtools 1.24 | core image | Passed. `sort -@ -o`, `fastq -F -@`, `index` and `coverage` are in the subcommand help. |
| kraken2 2.17.2 | `quay.io/biocontainers/kraken2:2.17.2--pl5321h3be2455_0` | Failed, then fixed. `--db`, `--threads`, `--confidence`, `--report` and `--memory-mapping` match. `--output -` does not write stdout. The help text says `-` suppresses normal output. Removed `--output -` so the classifications go to stdout and into the gzip. Gzipped input is auto-detected for a regular file. |
| bracken | `quay.io/biocontainers/bracken:3.1p1--hc52dbad_0` | Passed. `-d -i -o -w -r -l -t` match `bracken -h`. `bracken -v` prints `Bracken v3.0.1` inside the 3.1p1 image. |
| krona 2.7.1 | `quay.io/biocontainers/krona:2.7.1--pl526_0` | Passed. `ktImportText -o` matches the usage text. |
| sylph 1.0.0 | `quay.io/biocontainers/sylph:1.0.0--hb42e459_0` | Passed. `sylph profile` accepts positional `.syldb` and FASTQ files, `-t` and `-o`. `sylph sketch` exists. No ONT flag is required. `--read-seq-id` applies only with `-u`. `--sylph_args` stays empty. |
| emu 3.6.2 | `quay.io/biocontainers/emu:3.6.2--hdfd78af_0` | Passed. `abundance --db --type map-ont --threads --output-dir --output-basename --keep-counts` match. The script writes `{dir}/{basename}_rel-abundance.tsv`. |
| flye 2.9.6-b1802 | `quay.io/biocontainers/flye:2.9.6--py312h734f728_1` | Passed. `--nano-hq`, `--meta`, `--threads` and `--out-dir` match. `--nano-hq` is the R10 / Q20 preset. |
| medaka 2.2.2 | `quay.io/biocontainers/medaka:2.2.2--py312h3050eb1_0` | Passed as a flag check. `medaka_consensus -i -d -o -t -m` matches its help. `medaka tools list_models` includes `r1041_e82_400bps_sup_v5.0.0`. The image default is `r1041_e82_400bps_sup_v5.2.0`. The weights file is not in the image. Phase 4 records that failure and the fix. The parameter was not changed. The script writes `{outdir}/consensus.fasta`. |
| SemiBin2 2.6.0 | `quay.io/biocontainers/semibin:2.6.0--pyhdfd78af_0` | Passed. `single_easy_bin -i -b -o --sequencing-type long_read --environment human_gut --threads --compression none` match. `human_gut` is a listed environment. `long_read` and `none` are listed values. Bins are `output_bins/bin.<label>.fa` when compression is `none`. |
| CheckM2 1.1.0 | `quay.io/biocontainers/checkm2:1.1.0--pyhdfd78af_2` | Passed. `predict --threads --input --output-directory -x fa --database_path --force` match. The package writes `quality_report.tsv`. |
| GTDB-Tk 2.8.0 | `quay.io/biocontainers/gtdbtk:2.8.0--pyhdfd78af_0` | Failed, then fixed. `--genome_dir`, `--out_dir`, `--extension` and `--cpus` match. `--skip_ani_screen` is not in `classify_wf --help`. Removed it. |
| AMRFinderPlus 4.2.7 | `quay.io/biocontainers/ncbi-amrfinderplus:4.2.7--hf69ffd2_0` | Passed. `--nucleotide`, `--plus`, `--threads`, `--database` and `-o` match. `--ident_min` and `--coverage_min` are fractions from 0 to 1. The workflow does not pass them. The 90% filters stay in `amr_linkage.py`. |
| geNomad 1.13.0 | `quay.io/biocontainers/genomad:1.13.0--pyhdfd78af_0` | Passed. `end-to-end --cleanup --threads INPUT OUTPUT DATABASE` matches. |
| pyrodigal 3.7.1 | `quay.io/biocontainers/pyrodigal:3.7.1--py312h247cb63_1` | Passed. `-i -p meta -a -f gff -o -j` match. `-p` accepts `single` or `meta`. A 75 bp contig run with `-p meta` exited 0. |
| eggNOG-mapper 2.1.15 | `quay.io/biocontainers/eggnog-mapper:2.1.15--pyhdfd78af_0` | Passed. `-i --itype proteins -o --output_dir --data_dir --cpu --override` match. Annotations are `{output_dir}/{prefix}.emapper.annotations`. |

`modules/profiling.nf` and `modules/assembly.nf` are the only files changed. The stub blocks were not changed, so the Phase 2 stub was not re-run.

## 2026-10-28 — Phase 4: real tools on a small public mock

Nothing in this phase was committed, and no image was pushed. Inputs and outputs are under `/tmp/panbiome-phase4/`, outside the repo. `nextflow.config` was not edited. The run used `--big_memory '8 GB'` and `--threads 4` because the config default `big` label is 32 GB and the Docker VM reports about 31.3 GB.

### Inputs

| Item | What was used | Result |
| --- | --- | --- |
| Reads | `curl -r 0-209715199` of `https://ftp.sra.ebi.ac.uk/vol1/fastq/ERR290/007/ERR2906227/ERR2906227.fastq.gz` | Passed. 209715200 bytes. The object is 13981002932 bytes (ENA `fastq_bytes` for ERR2906227, Zymo-GridION-EVEN-BB-SN, ONT WGS, 3491078 reads). This is the start of the gzip stream, not a random subsample. `seqtk` and `rasusa` are not installed, and the full file is over 1 GB. The truncated gzip was repaired to 52677 reads and 208636938 bases. |
| Taxonomy | `curl` of `https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz` | Passed. Content-Length 79941140. |
| Genomes | RefSeq `*_genomic.fna.gz` for the ten accessions below | Passed. 18972118 bytes in total. Each file was under 6 MB. |
| Host decoy | `efetch` of NC_001416.1, then `minimap2 -x map-ont -d host/lambda.mmi` in the core image | Passed. Header `NC_001416.1 Enterobacteria phage lambda, complete genome`, 49254 bytes. Not a human genome. |
| Kraken2 | `kraken2-build --download-taxonomy --skip-maps`, `--add-to-library`, `--build --threads 4 --max-db-size 4294967296` in `kraken2:2.17.2` | Passed after one retry. `rsync` to `ftp.ncbi.nlm.nih.gov` was connection refused. The already downloaded taxdump was placed in the database with `taxdump.dlflag`, and `--skip-maps` was set so the multi-GB accession maps were not fetched. Sequences were tagged `kraken:taxid\|<strain taxid>` from each assembly report. Build: 44 sequences, 62370810 bp, hash table 109663084 bytes. |
| Bracken | `bracken-build -d db/kraken2 -t 4 -k 35 -l 1000` in the Bracken image | Passed. That image's `kraken2 --version` is 2.17.1. It classified all 44 sequences of the 2.17.2 database and wrote `database1000mers.kmer_distrib`. |
| Sylph | `sylph sketch -t 4 -g genomes_tagged/*.fna -o db/zymo_mock` | Passed. `db/zymo_mock.syldb`, 2.3 MB. |

Assembly reports supplied the strain taxids. Species names below are the scientific name of the species ancestor in this taxdump. Zymo still labels the fermentum genome as Lactobacillus fermentum. NCBI's scientific name for taxid 1613 is Limosilactobacillus fermentum.

| Accession | Strain taxid | Species |
| --- | --- | --- |
| GCF_000005845.2 | 511145 | Escherichia coli |
| GCF_000009045.1 | 224308 | Bacillus subtilis |
| GCF_000013425.1 | 93061 | Staphylococcus aureus |
| GCF_000006765.1 | 208964 | Pseudomonas aeruginosa |
| GCF_000196035.1 | 169963 | Listeria monocytogenes |
| GCF_000007785.1 | 226185 | Enterococcus faecalis |
| GCF_000006945.2 | 99287 | Salmonella enterica |
| GCF_000010145.1 | 334390 | Limosilactobacillus fermentum |
| GCF_000146045.2 | 559292 | Saccharomyces cerevisiae |
| GCF_000149245.1 | 235443 | Cryptococcus neoformans |

Sample sheet: `barcode01,ZYMO,test_sample,mock`. One test sample, so assembly is allowed and the control gate stays MISSING unless a control row is added. That is the patient-sample path.

### Run 1 — profiling, assembly off

Command, from the repo, Nextflow 23.10.0, `-profile standard`:

```
nextflow run main.nf -profile standard -ansi-log false \
  -w /tmp/panbiome-phase4/work \
  --fastq /tmp/panbiome-phase4/fastq_pass \
  --sample_sheet /tmp/panbiome-phase4/sample_sheet.csv \
  --host_ref /tmp/panbiome-phase4/host/lambda.mmi \
  --kraken2_db /tmp/panbiome-phase4/db/kraken2 \
  --sylph_db /tmp/panbiome-phase4/db/zymo_mock.syldb \
  --sylph_lineage_map /tmp/panbiome-phase4/db/sylph_lineage.tsv \
  --skip_assembly --skip_binning \
  --big_memory '8 GB' --threads 4 \
  --out_dir /tmp/panbiome-phase4/output
```

Passed. Exit 0. Session `deadly_caravaggio`. 18 tasks, all COMPLETED. Wall clock about 2 minutes (19:07:46Z to 19:09:51Z).

| Check | Result |
| --- | --- |
| Host depletion | Passed. 1 of 14140 filtered reads matched phage lambda (`host_fraction` 0.00007). Human reads were not used. |
| Kraken2 / Bracken | Passed. Bracken `-l S` named all ten species. Estimated reads: S. aureus 2338, E. faecalis 2131, L. monocytogenes 1985, L. fermentum 1029, B. subtilis 865, E. coli 832, S. enterica 755, S. cerevisiae 442, P. aeruginosa 345, C. neoformans 96. No other species. |
| Sylph | Passed as a command. Default `sylph profile` reported eight genomes, adjusted ANI 95.84 to 99.05. It did not emit B. subtilis or C. neoformans. |
| Reconcile `both` | Passed. Kept the eight species both methods called. Dropped B. subtilis (Bracken only, 865 reads) and C. neoformans (Bracken only, 96 reads). `min_ani` 95 was not changed. Listeria was kept at ANI 95.84. |
| Reports | Passed. `wf-gut-report.html` and `samples/ZYMO/ZYMO.sample_report.html` were written. The sample report names the eight kept species. The run report shows control status MISSING and a Salmonella watchlist alert. Background is white. |
| QC | Passed as a gate, and the sample is FAIL. 52677 raw reads, 14140 after chopper `--quality 10 --minlength 500`, 0.063 Gb. FAIL is the placeholder minimum of 100000 reads and 1.0 Gb. Flags also note raw mean Q 8.85, an unknown basecall model, and adapters on 49.98% of raw reads. Filtered mean Q in `ZYMO.filtered.stats.json` is 10.38. Thresholds were not changed. |
| Trace | Highest peak RSS was Kraken2 at 295.6 MB. Host depletion 191.1 MB. Filter 95.8 MB. No label was changed. These peaks are for 0.06 Gb of filtered reads, not a 3–4 Gb sample, so the 32 GB default was left in place. |

The abundance skew against Zymo's even mix (about 12% genomic DNA for each bacterium and 2% for each yeast) is expected. The file is a prefix, then a quality filter. The species set is the mock set.

### Run 2 — assembly on, binning off

Failed at `MEDAKA (ZYMO)`. Exit 1. Session `serene_snyder`. Started 2026-10-27T19:11:49Z. Same arguments as run 1, without `--skip_assembly`. Work directory `/tmp/panbiome-phase4/work_asm`, output `/tmp/panbiome-phase4/output_asm`.

```
nextflow run main.nf -profile standard -ansi-log false \
  -w /tmp/panbiome-phase4/work_asm \
  --fastq /tmp/panbiome-phase4/fastq_pass \
  --sample_sheet /tmp/panbiome-phase4/sample_sheet.csv \
  --host_ref /tmp/panbiome-phase4/host/lambda.mmi \
  --kraken2_db /tmp/panbiome-phase4/db/kraken2 \
  --sylph_db /tmp/panbiome-phase4/db/zymo_mock.syldb \
  --sylph_lineage_map /tmp/panbiome-phase4/db/sylph_lineage.tsv \
  --skip_binning \
  --big_memory '8 GB' --threads 4 \
  --out_dir /tmp/panbiome-phase4/output_asm
```

Flye had written an assembly. Medaka then exited during model setup. `medaka tools list_models` includes `r1041_e82_400bps_sup_v5.0.0`, and that name was left unchanged. The image only ships other weight files. `resolve_model` in this image looks in `/usr/local/lib/python3.12/site-packages/medaka/data` and `/root/.medaka/data`, downloads with `model_url_template` `https://github.com/nanoporetech/{pkg}/raw/master/{pkg}/{subdir}/{fname}`, and uses suffix `_model_pt.tar.gz`. The download of `r1041_e82_400bps_sup_v5.0.0_model_pt.tar.gz` succeeded. Both stores are not writable as the container user (`-u $(id -u):$(id -g)`). The error text then crashed because the first store is a `PosixPath`:

```
RuntimeError: Error validating model from '--model' argument: sequence item 0: expected str instance, PosixPath found
```

A range request of the template URL returned `content-range: bytes 0-0/1501952` (1.5 MB). Under 1 GB, so it was allowed.

Fix, in `modules/assembly.nf` only: when `--medaka_model` is a name rather than a file, the task builds that same URL from the image's template and suffix, refuses a body over 1 GiB, checks `open_model`, and passes the work-directory path to `medaka_consensus -m`. A filepath returns from `resolve_model` without writing a model store. The model name parameter is still `r1041_e82_400bps_sup_v5.0.0`. The stub block was not changed, and the Phase 2 stub was not re-run. `nextflow.config` was not edited.

### Run 3 — same assembly command after the Medaka fix

Passed for Flye and Medaka. The workflow then exited 1 at `AMRFINDER`. Session `disturbed_snyder`. 2026-10-27T19:28:46Z to 2026-10-27T19:39:36Z. Work directory `/tmp/panbiome-phase4/work_asm2`, output `/tmp/panbiome-phase4/output_asm2`. Run 2's work directory was left in place.

```
nextflow run main.nf -profile standard -ansi-log false \
  -w /tmp/panbiome-phase4/work_asm2 \
  --fastq /tmp/panbiome-phase4/fastq_pass \
  --sample_sheet /tmp/panbiome-phase4/sample_sheet.csv \
  --host_ref /tmp/panbiome-phase4/host/lambda.mmi \
  --kraken2_db /tmp/panbiome-phase4/db/kraken2 \
  --sylph_db /tmp/panbiome-phase4/db/zymo_mock.syldb \
  --sylph_lineage_map /tmp/panbiome-phase4/db/sylph_lineage.tsv \
  --skip_binning \
  --big_memory '8 GB' --threads 4 \
  --out_dir /tmp/panbiome-phase4/output_asm2
```

| Check | Result |
| --- | --- |
| Medaka | Passed. Log line: `Using model: .../r1041_e82_400bps_sup_v5.0.0_model_pt.tar.gz`. That file is 1501952 bytes. `medaka 2.2.2`. Consensus written. Exit 0. Realtime 5m 45s, peak RSS 7 GB, peak vmem 7.8 GB. |
| Flye | Passed. Exit 0. Realtime 3m 14s, peak RSS 695.6 MB. Draft `ZYMO.flye.fasta`: 467 contigs, 7928514 bp, N50 20795, longest 100646. `assembly_info.txt` coverage on that contig is 5. |
| Polished contigs | 467 contigs, 7858240 bp, N50 20573, longest 100122. Work directory `/tmp/panbiome-phase4/work_asm2/14/0cd29e9fd82dff5a795701f858269f/ZYMO.contigs.fasta`. `MEDAKA` has no `publishDir`, so this file is only in the work directory. |
| Species table | Passed. `output_asm2/.../ZYMO.species.tsv` matches run 1. Eight species kept. B. subtilis and C. neoformans dropped. Watchlist: Salmonella enterica. |
| QC and control | Same files as run 1. QC status FAIL. Control status MISSING. |
| HTML report | Not run. `BUILD_REPORT` did not start, because `AMRFINDER` stopped the workflow. Run 1 still has `wf-gut-report.html` and `ZYMO.sample_report.html` for this species table. |
| AMRFinder | Not run. Exit 1: `No valid AMRFinder database is found` (`/usr/local/share/amrfinderplus/data/latest` is absent). The latest database was measured at 129839548 bytes and was not downloaded. `--amrfinder_db` was unset. geNomad and eggNOG stayed off. |
| Trace | 19 tasks in `output_asm2/execution/trace.txt`. Profiling peaks match run 1 (Kraken2 291.4 MB, host depletion 190.8 MB). Highest peak is Medaka at 7 GB. The task completed inside the 8 GB CLI override. `nextflow.config` still has `big_memory` 32 GB. That default was left in place. This input is 0.06 Gb of filtered reads. The 32 GB label is the production setting for a 3–4 Gb sample. |
| Binning | Not run. `--skip_binning` was set. The trace has no `MAP_CONTIGS`, SemiBin2, CheckM2 or GTDB-Tk task. |

### Binning

Not run. No CheckM2 database was supplied, and SemiBin2 downloads GTDB (the help text says more than 100 GB) when `--reference-db` is unset. Binning stays off until a reference database is supplied or that download is approved.

## 2026-10-28 — Phase 5: full databases, sizes only

No database was downloaded. `df` on the data volume reported about 84 GiB free. Commands were read from the pinned image `--help` or from the publisher page, then the file size was read with a one-byte range request where a URL was named.

| Database | Result |
| --- | --- |
| T2T-CHM13v2.0 | Passed as a size check. `https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/009/914/755/GCA_009914755.4_T2T-CHM13v2.0/GCA_009914755.4_T2T-CHM13v2.0_genomic.fna.gz` returned `bytes 0-0/932696125`. `minimap2 -x map-ont -d` was already used on the lambda decoy in Phase 4. The CHM13 index was not built. |
| Kraken2 GTDB | Passed as a size check. The Langmead index page (June 2026 table) lists GTDB v226 `genomic_files_reps`, archive dated 2025-06-09, extracted index 644.0 GB, Bracken lengths 50 through 300. `https://genome-idx.s3.amazonaws.com/kraken/k2_gtdb_genome_reps_20250609.tar.gz` returned `bytes 0-0/537801719465`. `bracken-build -d DB -t THREADS -k 35 -l 1000` remains the command that writes the 1000-mer file this workflow reads. Struo2 was not confirmed, so that example was removed from `docs/DATABASES.md`. |
| sylph GTDB r226 | Passed as a size check. Pinned sylph 1.0.0 `profile --help` accepts `*.syldb` and `*.syl2db`. `http://faust.compbio.cs.cmu.edu/sylph-stuff/gtdb-r226-c200-dbv2.syl2db` returned `bytes 0-0/14272284891`. The sylph pre-built database page calls this the r226 `-c 200` two-stage file. r232 was not selected, because the Kraken prebuilt is v226. |
| Lineage map | Passed as a size check. `bac120_taxonomy_r226.tsv.gz` is 7607942 bytes and `ar53_taxonomy_r226.tsv.gz` is 227138 bytes, both under `https://data.gtdb.ecogenomic.org/releases/release226/226.0/`. `bin/make_sylph_lineage_map.py` takes those two files. The old r220 example was the wrong release for this pair. |
| CheckM2 | Passed as a command and size check. Image help: `checkm2 database --download --path DIR`. Zenodo record 14897628, `checkm2_database.tar.gz`, 1735095710 bytes. The README names `CheckM2_database/uniref100.KO.1.dmnd` for `--database_path`. Not downloaded. |
| AMRFinderPlus | Command passed. `amrfinder_update --database DIR` and `amrfinder -u` are both in the 4.2.7 image. The Phase 4 HEAD of `latest/` remains 129839548 bytes. Not downloaded. |
| geNomad | Passed as a command and size check. Image 1.13.0 reads `https://portal.nersc.gov/genomad/__data__/releases.txt` and, for package 1.13, selects `genomad_db_v1.9.tar.gz`. That file returned `bytes 0-0/842023773`. `genomad download-database DIR` matches the image help. The README says the unpacked folder is `genomad_db`. Not downloaded. |
| eggNOG | Failed as a download command. `download_eggnog_data.py --data_dir` is the right flag, and the default includes the DIAMOND file unless `-D`. The script's host `eggnogdb.embl.de` did not resolve. Image DB version is 5.0.2. The same three names on `https://eggnog5.embl.de/download/emapperdb-5.0.2/` returned 6776977123, 72797584 and 5208806170 bytes. The workflow still passes only `--data_dir`. Not downloaded. The current eggNOG-mapper v3 / eggNOG 7 download does not apply to image 2.1.15. |
| GTDB-Tk | Passed as a command and size check. Optional. Image `gtdbtk --version` is 2.8.0. The 2.8.0 install page says R232 is the package for tool versions 2.7.0 through current, and R226's maximum tool is 2.6.1. `gtdbtk_r232_data.tar.gz` returned `bytes 0-0/60806405195`. The page says about 100 GB of external data and about 140 GB of memory for bacteria. The workflow sets `GTDBTK_DATA_PATH` from `--gtdbtk_db`. Not downloaded. |
| Emu | Not confirmed. The image has `emu build-database`. No current prebuilt URL was checked. |

`docs/DATABASES.md` was corrected for the r226 shotgun pair, the Langmead Kraken URL, the Bracken 1000-mer gap, the GTDB-Tk R232 command, the geNomad output directory, and the eggNOG host. No image was pulled and `nextflow.config` was not edited.

## 2026-10-28 — Phase 6: hygiene

`nextflow.config` params were unchanged, so `scripts/make_schema.py` was not run. `manifest.version` was set to `0.1.1` after the checks below. The core image tag stays `0.1.0`. No image was pulled or pushed. `nf-core` is not installed (`python3 -c "import nf_core"` raised `ModuleNotFoundError`, and `command -v nf-core` was empty), so `nf-core pipelines lint` was not run.

| Check | Result |
| --- | --- |
| `python3 -m pytest tests -q` | Passed. 8 passed in 6.98s, then again in 6.37s after the manifest version change. |
| `nextflow config -profile standard` | Passed. Exit 0. `manifest.version` is `0.1.1`. `docker.enabled` is true. `docker.runOptions` is `-u $(id -u):$(id -g)`. `big_memory` is `32 GB`. Captured in `/tmp/panbiome-phase6/nextflow_config_v011.txt`. |
| `nextflow inspect main.nf -profile standard` | The bare command exited 1 with `Please provide --fastq`. |
| `nextflow inspect` with `test_data/fastq_pass`, the synthetic sample sheet, `test_data/stub_db/host.mmi`, and `test_data/stub_db/kraken2` | Passed. Exit 0. 22 processes, each container equal to the matching `params.container_*` tag. |
| Same inspect with `--assay both` plus `--sylph_db`, `--emu_db`, `--checkm2_db`, `--gtdbtk_db`, `--genomad_db`, `--eggnog_db`, and `--amrfinder_db` pointed at `test_data/stub_db` | Passed. Exit 0. 32 processes. Containers: core `ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0`; Kraken2 `quay.io/biocontainers/kraken2:2.17.2--pl5321h3be2455_0`; Bracken `quay.io/biocontainers/bracken:3.1p1--hc52dbad_0`; Krona `quay.io/biocontainers/krona:2.7.1--pl526_0`; sylph `quay.io/biocontainers/sylph:1.0.0--hb42e459_0`; Emu `quay.io/biocontainers/emu:3.6.2--hdfd78af_0`; Flye `quay.io/biocontainers/flye:2.9.6--py312h734f728_1`; Medaka `quay.io/biocontainers/medaka:2.2.2--py312h3050eb1_0`; SemiBin2 `quay.io/biocontainers/semibin:2.6.0--pyhdfd78af_0`; CheckM2 `quay.io/biocontainers/checkm2:1.1.0--pyhdfd78af_2`; GTDB-Tk `quay.io/biocontainers/gtdbtk:2.8.0--pyhdfd78af_0`; AMRFinderPlus `quay.io/biocontainers/ncbi-amrfinderplus:4.2.7--hf69ffd2_0`; geNomad `quay.io/biocontainers/genomad:1.13.0--pyhdfd78af_0`; Pyrodigal `quay.io/biocontainers/pyrodigal:3.7.1--py312h247cb63_1`; eggNOG-mapper `quay.io/biocontainers/eggnog-mapper:2.1.15--pyhdfd78af_0`. |
| `HOST_SKIP`, `UNPOLISHED_CONTIGS` | Not in that inspect. Host depletion was on and polish was on, so those two processes were outside the graph. Both scripts set `container params.container_core`. |

`README.md` verification status now names the synthetic stub sheet and the ERR2906227 prefix. The example sylph path is the GTDB r226 `.syl2db`. `CHANGELOG.md` records the v0.1.1 fixes. The stub run was not repeated.

