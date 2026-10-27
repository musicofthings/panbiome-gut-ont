# panbiome-gut-ont

Oxford Nanopore gut microbiome workflow for human stool, written in Nextflow (DSL2) and laid out to import into the **EPI2ME** desktop app. Built for Panbiome: 16 stool samples per PromethION flow cell, whole-genome shotgun, 3 to 4 Gb per sample, run on a washed flow cell after a PGx library.

> **Status: v0.1.1.** Python helpers and the parameter schema are unit-tested. The stub DAG passed on synthetic `test_data/`. Kraken2, Bracken, sylph, Flye, and Medaka passed on a 200 MB prefix of public Zymo ONT run ERR2906227 with a ten-genome database and a phage-lambda host decoy. SemiBin2, CheckM2, GTDB-Tk, AMRFinderPlus, geNomad, eggNOG, and Emu have not been run on real databases. See [Verification status](#verification-status) and [CHANGELOG.md](CHANGELOG.md).

## What it does

```
FASTQ / uBAM (per barcode) + sample sheet
  -> validate sample sheet (rejects barcodes used by the earlier PGx library)
  -> read stats (correct mean Q, basecall model sup/hac/fast, adapter prevalence) -> chopper filter
  -> host depletion (minimap2; human reads counted and discarded, PGx-carryover count)
  -> species profiling
       shotgun: Kraken2 + Bracken  and  sylph  -> reconcile (both methods must agree by default)
       16S:     Emu
  -> assembly (metaFlye) -> Medaka polish -> SemiBin2 bins -> CheckM2 (-> GTDB-Tk)
  -> AMRFinderPlus (+ virulence) , geNomad plasmids, Pyrodigal -> eggNOG-mapper -> function summary
  -> AMR/gene linkage to contig, circularity, plasmid, MAG and taxon (genotype only)
  -> control status (in-run controls, or the latest scheduled control run)
  -> alpha/beta diversity, PCoA, PERMANOVA, rarefaction, BIOM
  -> run report + one report per sample (self-contained HTML)
```

## Run it in EPI2ME

1. Build and push the core image once (it holds the Python helpers, minimap2, samtools, chopper):
   `docker build -t ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0 -f docker/Dockerfile docker && docker push ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0`
   (or run the `build-core-image` GitHub Action). Make the package public, or change `container_core`.
2. Push this folder to `github.com/musicofthings/panbiome-gut-ont`.
3. In EPI2ME: **Workflows > Import workflow > Import from GitHub**, enter `musicofthings/panbiome-gut-ont`. The settings form is generated from `nextflow_schema.json`.
4. Prepare databases ([docs/DATABASES.md](docs/DATABASES.md)) and set their paths in the form.
5. Pick `fastq_pass` as the input, choose the sample sheet, and start.

Command line (same thing):

```bash
nextflow run musicofthings/panbiome-gut-ont -profile standard \
  --fastq /data/run1/fastq_pass --sample_sheet samples.csv --out_dir results \
  --host_ref chm13v2.0.map-ont.mmi --pgx_barcodes barcode01,barcode02 --pore_count 6200 \
  --kraken2_db /db/kraken2_gtdb_r226 --sylph_db /db/gtdb-r226-c200-dbv2.syl2db --sylph_lineage_map /db/gtdb_r226_map.tsv \
  --checkm2_db /db/checkm2/uniref100.KO.1.dmnd --amrfinder_db /db/amrfinder \
  --genomad_db /db/genomad --eggnog_db /db/eggnog \
  --control_summary controls/control_summary.json
```

## Sample sheet

```csv
barcode,alias,type,group,subject_id,collection_date,extraction_lot
barcode04,P001,test_sample,baseline,S01,2026-10-20,L7
barcode05,P002,test_sample,baseline,S02,2026-10-20,L7
```

`type` is `test_sample`, `positive_control`, `negative_control` or `no_template_control`. Extra columns are carried into the reports. `--required_metadata subject_id,collection_date` makes columns mandatory.

## Controls without in-run controls

Panbiome patient runs carry no controls. Instead, run a blank and a mock community on a fixed schedule (each new reagent or kit lot, each instrument or operator change, and at least monthly) as a normal run with `negative_control` and `positive_control` rows and `--mock_expected mock.tsv`. That run writes `run/controls/control_summary.json`. Later patient runs pass it with `--control_summary`. The report banner then shows `PASS`, `FAIL`, `EXPIRED` (older than `--control_max_age_days`, default 31) or `MISSING`. Taxa in patient samples that also appear in the blank are flagged as possible reagent contaminants.

## Washed flow cell, second library

* `--pgx_barcodes` rejects any gut barcode that the PGx library used.
* `--pgx_regions` (BED in host-reference coordinates) counts human reads in PGx target regions as likely carryover and warns above 100 reads.
* Human reads are never written to disk; only non-host reads continue.
* `--pore_count` and `--run_hours` are recorded in the report. The Flow Cell Check is not valid after a wash, so use the first pore scan.
* Per-sample yield is checked against `--target_gb` (3.0) and `--min_gb` (1.0), and against the run median to catch pooling imbalance.

## Outputs

```
output/
  wf-gut-report.html            run report (QC, controls, composition, diversity, AMR, MAGs)
  run/                          sample sheet, qc_summary.*, controls/, diversity/ (tables, BIOM, PNGs)
  samples/<alias>/
    <alias>.sample_report.html
    qc/ taxonomy/ assembly/ bins/ resistance/ function/
  execution/                    params.json, software_versions.txt, timeline, trace
```

## Things you must set during validation

All thresholds are placeholders: QC limits, mock limits (`mock_max_bray`, `mock_max_unexpected`), Kraken2 confidence, minimum species reads, sylph ANI, AMR identity and coverage, and the watchlist abundance thresholds. Fix them with the mock community and a pilot run, then lock the pipeline and database versions. See [docs/FEATURE_COVERAGE.md](docs/FEATURE_COVERAGE.md) for what is and is not built compared with the requirements spec.

## Verification status

| Part | Status |
| --- | --- |
| Python helpers (`bin/`) | Passed. `python3 -m pytest tests -q` on 2026-10-28: 8 passed. Synthetic unit tests. |
| Parameter schema vs `nextflow.config` | Passed. Params are unchanged, so `scripts/make_schema.py` was not re-run. The same pytest checks every `params` key and default. |
| Nextflow DAG, channel wiring, `-stub-run` | Passed on the synthetic sheet in `test_data/` (P001, P002, BLANK1). `bash tests/stub_run.sh` after the stub fix: 48 tasks and one sample report each. Also passed: `--assay 16s`, `--assay both`, `--skip_assembly`, `--skip_host_depletion`, `--control_summary`. The stub was not re-run after the Kraken2, GTDB-Tk, and Medaka script edits. Those edits left the stub blocks as they were. |
| Kraken2, Bracken, sylph, host depletion, QC, reconcile, HTML report | Passed on small data. First 209715200 bytes of ENA ERR2906227 (repaired to 52677 reads, 208636938 bases). Kraken2, Bracken, and sylph used the same ten RefSeq genomes. Host decoy: Enterobacteria phage lambda NC_001416.1. Run 1 used `--skip_binning --skip_assembly` and exited 0. Eight species were kept where both methods agreed. |
| Flye and Medaka | Passed on small data. Same reads and databases, run 3. Flye: 467 contigs, 7928514 bp, N50 20795. Medaka: 467 contigs, 7858240 bp, N50 20573, model file `r1041_e82_400bps_sup_v5.0.0_model_pt.tar.gz`. |
| SemiBin2, CheckM2, GTDB-Tk, geNomad, eggNOG, Emu | Not run on real data. |
| AMRFinderPlus | Not run. With no `--amrfinder_db`, the pinned image exited 1 because `/usr/local/share/amrfinderplus/data/latest` is absent. |
| Container tags | Passed as a resolution check on 2026-10-28. `nextflow inspect -profile standard` mapped each included process to the tag in `nextflow.config`. Core image `ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0` was built locally (`e1dd5c49b4bc`, 2.04 GB) and has not been pushed. |

Details, commands, and trace peaks are in [docs/VALIDATION_LOG.md](docs/VALIDATION_LOG.md).

Assumptions checked in those runs:

- `--sylph_args` is still empty. Pinned sylph 1.0.0 accepts `.syldb` and `.syl2db`. No extra ONT flag is required for `sylph profile`. `--read-seq-id` applies only with `-u`. Empty args produced species calls on the ERR2906227 prefix.
- `medaka_model` is still `r1041_e82_400bps_sup_v5.0.0`. `medaka tools list_models` includes that name. The image default consensus model is `r1041_e82_400bps_sup_v5.2.0`. The v5.0.0 weights are downloaded into the work directory and passed as a file to `-m`.
- `bracken_read_len` is still 1000. The tiny database was built with `bracken-build -l 1000`. The Langmead GTDB v226 archive ships Bracken lengths through 300-mers, so a full database still needs that 1000-mer build.
- The small run gave Kraken2 and sylph one shared taxonomy (those ten RefSeq genomes). The full-size pair in [docs/DATABASES.md](docs/DATABASES.md) is GTDB r226 for both. GTDB-Tk 2.8.0 takes reference package R232.
- SemiBin2 `--environment human_gut` and `--sequencing-type long_read` are listed values in the 2.6.0 help. Binning was not run. With `--reference-db` unset, `single_easy_bin` downloads GTDB.
- eggNOG-mapper is called with `--data_dir` only. In the pinned 2.1.15 help, `--dmnd_db` is optional when the DIAMOND file sits in that directory. The process was not run on a real database. The image download host `eggnogdb.embl.de` did not resolve. The eggNOG 5.0.2 files are on `https://eggnog5.embl.de/download/emapperdb-5.0.2/`.

Placeholder thresholds (QC, mock Bray-Curtis, AMR, watchlist) were not changed.

## Layout

`main.nf` workflow, `modules/` processes, `bin/` helper scripts, `assets/` watchlist and functional targets, `nextflow_schema.json` (generated by `scripts/make_schema.py`), `tests/` pytest and stub run, `docker/` core image.
