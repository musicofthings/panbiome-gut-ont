# Changelog

## Unreleased

### AWS

- `infra/aws/batch.yaml`: CloudFormation stack in `ap-south-1` with a private encrypted S3 bucket, an ECR mirror of the core image, IAM roles, and on-demand AWS Batch queues that scale to zero. Head jobs stop after 72 hours.
- Task machines' gp3 root volumes run at 1000 MB/s and 16000 IOPS, and the ECS agent waits 10 minutes, not 4, for a container to be created. While Kraken2 staged its 64 GB database at the default 125 MB/s, other tasks on the same machine failed with `DockerTimeoutError` (CheckM2 in the first `zymo-aws1` run, then `PARSE_SYLPH` on all three attempts in the second). Needs a stack update.
- `infra/aws/run.sh` launches any workflow on Batch. `PANBIOME_REMOTE=1` runs Nextflow itself as a Batch job.
- `infra/aws/fetch_dbs.nf` downloads sylph r226, CheckM2, geNomad, AMRFinderPlus, eggNOG 5.0.2 and the T2T-CHM13 index to S3. `infra/aws/build_kraken2.nf` builds a 64 GB GTDB r226 Kraken2 + Bracken database. Downloads resume after dropped connections (`infra/aws/bin/fetch_url`).
- `infra/aws/fetch_test_reads.nf` writes the first ~3 Gb of a public ONT run to S3. The default, `--dataset fecal`, is the ZymoBIOMICS Fecal Reference D6323 from EPI2ME `zymo_fecal_2025.05` (R10.4.1, Dorado SUP 5.0.0, flow cell PAU85136), streamed from the unaligned BAM with `samtools fastq`. Its first reads have median Q25. `--dataset mock` is ZymoBIOMICS mock run ERR2906227 (R9.4.1, median Q9.4), read from NCBI's SRA copy on AWS with `fastq-dump` (sra-tools 3.2.1), because on 2026-10-31 ENA served it at 11 KB/s over HTTPS and about 300 KB/s over HTTP or FTP.
- `infra/aws/run.sh` no longer uploads `api/` and `web/` with each launch. The head job saves Nextflow's task cache to `s3://BUCKET/launch/<run>/.nextflow/`, and `PANBIOME_RESUME=1` reruns a run with `-resume`.
- New `awsbatch` profile in `nextflow.config`. It also retries a task whose container never starts (`DockerTimeoutError` has no exit status), which had stopped the first `zymo-aws1` run at CheckM2.
- `infra/aws/kraken2_check.nf` classifies one read file at several `--confidence` values and saves `kraken2-inspect`'s header. AWS runs with the 64 GB Kraken2 build use `--kraken2_confidence 0.005`; the default stays 0.05 for a full database ([docs/DATABASES.md](docs/DATABASES.md)).

### Run monitor

- Report viewer (`/runs/<run>/report`): run QC for every sample, then per sample the read statistics with length and quality histograms, human reads removed, species (top 20 chart, watchlist, searchable table), alpha diversity, MAG quality (completeness against contamination), AMR genes with plasmid and bin context, and targeted gut functions and KEGG modules. Built from the files a run already writes (`api/panbiome_api/report.py`).
- Files page: browse `uploads/`, `results/` and `test_data/` in the data bucket, download with presigned links, and upload files or whole run folders by drag and drop. Uploads go from the browser straight to S3 as multipart uploads with presigned part URLs (4 parts and 2 files at a time, retries, cancel, overwrite check), so large FASTQ/BAM files never pass through Lambda (`api/panbiome_api/files.py`, `web/src/uploads.ts`). Writes are limited to `uploads/`. Needs the web stack redeployed and the Batch stack's new `UploadOrigins` parameter for the bucket's CORS rule.
- `api/` (FastAPI) and `web/` (React + Vite): a read-only run monitor for AWS Batch runs. It lists runs and shows the step graph with live per-sample task status, the Nextflow log, task logs, parameters and reports. Status comes from AWS Batch and `trace.txt`, with no change to the workflow. Runs locally with your SSO login ([docs/MONITOR.md](docs/MONITOR.md)).
- `infra/aws/web.yaml` and `infra/aws/deploy_web.sh` host it: an invite-only Cognito user pool with TOTP MFA and managed login, the API on Lambda (`panbiome_api.lambda_handler`) behind an HTTP API with a JWT authorizer, and the web build on a private S3 bucket behind CloudFront, which also routes `/api/*` so the browser makes same-origin calls. The web app signs in with the authorization code grant and PKCE when the site serves `/config.json`. Not deployed yet.

### Performance and fault tolerance

- Database cache on each AWS Batch machine: with `--db_cache` (on in the `awsbatch` profile) a task gets the S3 path of its database and `bin/dbcache` copies it once per machine into `/mnt/dbcache`, with a lock so tasks that start together share one download. Processes take databases as `tuple path(db), val(db_uri)`; without the cache they are staged as before (`main.nf` `dbInput`, `assets/NO_DB`).
- `infra/aws/batch.yaml`: 500 GB task disks; `/mnt/dbcache`; AWS CLI S3 settings for the cache (64 concurrent 64 MB parts); an ECR pull-through cache for quay.io images; compute environment updates wait up to 6 hours for running jobs. Needs a stack update.
- `nextflow.config` `awsbatch`: 16 parallel transfers per task (was 4) and the `/mnt/dbcache` volume.
- `infra/aws/run.sh`: remote runs use Nextflow's cloud cache (`s3://BUCKET/cache/`) with a saved session id, so `PANBIOME_RESUME=1` resumes even after the head machine was lost; the head job is retried once when its machine is terminated and resumes by itself. For `main.nf` the databases under `s3://BUCKET/db/` are preset (`infra/aws/databases.config`, with `--kraken2_confidence 0.005`). Tool images come from the ECR cache once it exists.
- Reads are recompressed with `bgzip -@ <cpus> -l 1` instead of single-threaded `gzip -6` in `INGEST` and `FILTER_READS`, and decompressed with threads.
- `HOST_DEPLETION` runs `minimap2 -c` to PAF and `bin/host_split.py` makes one pass over the reads, instead of parsing full SAM in Python and writing gzip level 9 (44 min for 3 Gb). The host rule is unchanged: the PAF query span of a base-level alignment equals the CIGAR's M/I/=/X count. On 400 simulated reads (human, part-human, reverse strand, non-human) the old and new versions kept the same reads with identical sequences.
- `FLYE` runs with `--iterations 0` when Medaka polishes afterwards (Flye docs: 0 skips Flye's own polishing).
- `bin/dbcache` downloads with the AWS CLI's CRT transfer client (`preferred_transfer_client = crt`, `target_bandwidth` 8 Gb/s, buffers capped at 2 GiB). In `zymo-fecal2` the default client fetched the 64 GB Kraken2 database in 475 s and eggNOG in 346 s, about 140 MB/s. With CRT, a test job in an 8 GB container fetched them in 69 s (66.6 GB) and 52 s (48.6 GB), close to the disk's 1000 MB/s. The S3 settings file in the launch template is no longer used and was removed.
- `EGGNOG` runs the DIAMOND search and the annotation as two `emapper.py` calls and logs each one's time. New `--eggnog_dbmem` (on in the `awsbatch` profile, with 56 GB for the task) loads the 38.5 GB `eggnog.db` into memory for the annotation (`--dbmem`, about 44 GB). Same search settings, so the same annotations.

### Workflow

- SemiBin2 always writes `<alias>_bins/.keep`, because S3 work directories cannot hold an empty folder (`modules/assembly.nf`).
- eggNOG creates `emapper_out` before `emapper.py`, which rejects an output folder that does not exist (`modules/assembly.nf`).

### Documentation

- `docs/AWS.md`, `docs/ROADMAP.md` (first real AWS run, web frontend, EPI2ME), README section "Run it on AWS". `docs/AWS.md` "Watching a run" lists the terminal commands.
- `docs/MONITOR.md`: how the run monitor gets its data, local setup, CORS.

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
