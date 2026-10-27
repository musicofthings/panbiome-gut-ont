# Changelog

## 0.1.1 — 2026-10-28

Fixes found while running the v0.1.0 draft. Parameter defaults are unchanged, including `medaka_model`, `bracken_read_len`, `sylph_args`, `min_ani`, `min_species_reads`, and `big_memory` (32 GB). The core image tag stays `ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0`. That image was not rebuilt. The workflow reads `bin/` from the project directory.

### Workflow

- The sample-sheet stub copies a supplied sheet. The report stub writes one `<alias>.sample_report.html` per row (`modules/ingest.nf`, `modules/reporting.nf`).
- Kraken2 classifications go to stdout. `--output -` was removed because that value suppresses output (`modules/profiling.nf`).
- GTDB-Tk `classify_wf` is called without `--skip_ani_screen`. That flag is absent from the 2.8.0 help (`modules/assembly.nf`).
- When `--medaka_model` is a model name, Medaka downloads `r1041_e82_400bps_sup_v5.0.0_model_pt.tar.gz` into the work directory, refuses a body over 1 GiB, and passes that path to `medaka_consensus -m`. The model name is unchanged (`modules/assembly.nf`).
- `workflow.onComplete` is assigned inside the entry workflow so Nextflow 25+ strict syntax accepts the script. The completion message is unchanged (`main.nf`).
- Sample `publishDir` paths that use `meta.id` are closures, so Nextflow 26 does not evaluate `meta` while the process is being defined.

### Documentation

- `docs/DATABASES.md` pairs Kraken2 and sylph on GTDB r226, names the Langmead archive, records the Bracken 1000-mer build, the GTDB-Tk R232 package, the geNomad `DIR/genomad_db` path, and the eggNOG host that did not resolve.

Commands and results are in `docs/VALIDATION_LOG.md`.
