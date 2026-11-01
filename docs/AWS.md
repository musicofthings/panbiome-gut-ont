# Running on AWS Batch

Databases live in S3 and tasks run on AWS Batch in `ap-south-1`. Nothing large is stored on the launching machine.

## Pieces

| File | What |
| --- | --- |
| `infra/aws/batch.yaml` | CloudFormation stack: private encrypted S3 bucket (`work/` expires after 14 days), ECR repository for the core image, IAM roles, and three job queues. |
| `infra/aws/run.sh` | Launches any of the workflows with the stack's bucket, job role and ECR image. |
| `infra/aws/web.yaml`, `infra/aws/deploy_web.sh` | Separate stack for the run monitor: Cognito sign-in, the API on Lambda, the site on S3 + CloudFront ([MONITOR.md](MONITOR.md)). |
| `infra/aws/fetch_dbs.nf` | Downloads sylph r226 + lineage map, CheckM2, geNomad, AMRFinderPlus, eggNOG 5.0.2 and the T2T-CHM13 minimap2 index into `s3://BUCKET/db/`. |
| `infra/aws/build_kraken2.nf` | Builds the 64 GB GTDB r226 Kraken2 + Bracken database into `s3://BUCKET/db/k2_gtdb_r226_64GB`. |
| `infra/aws/kraken2_check.nf` | Classifies one read file against a Kraken2 database at several `--confidence` values (`--confidences 0,0.05`) and writes the reports and `kraken2-inspect`'s header to `results/<run>/`. |
| `infra/aws/fetch_test_reads.nf` | Writes the first ~3 Gb of a public ONT run and a one-row sample sheet to `--reads_dir`. `--dataset fecal` (default): ZymoBIOMICS Fecal Reference D6323 from EPI2ME `zymo_fecal_2025.05` (flow cell PAU85136, R10.4.1, SUP 5.0.0), read from the unaligned BAM in `s3://ont-open-data`. `--dataset mock`: ZymoBIOMICS mock run ERR2906227 (R9.4.1) from NCBI's SRA bucket, because ENA was too slow. |

| Queue | Machines | Used by |
| --- | --- | --- |
| `panbiome-default` | On-demand m7i/r7i, 300 GB disk | `small` and `medium` tasks |
| `panbiome-ondemand` | Same compute environment as `panbiome-default` | `big` tasks (Kraken2, Flye, Medaka, binning, GTDB-Tk) |
| `panbiome-build` | On-demand r7i/r6i, 1000 GB disk | `build_kraken2.nf` only (16 vCPU, 120 GB) |
| `panbiome-ondemand` (head) | `panbiome-nextflow-head` job, 2 vCPU | Nextflow itself when `PANBIOME_REMOTE=1` |

Everything is on-demand; there is no spot capacity. Both compute environments have a minimum of 0 vCPUs, so Batch starts machines when jobs are queued and terminates them once no job needs them (normally within minutes). Nothing runs, and nothing is billed for compute, between runs. A head job is stopped after `HeadTimeoutSeconds` (default 72 hours), so a hung Nextflow run cannot keep machines up. What is billed while idle is S3 storage: about 79 GB of databases plus the 64 GB Kraken2 build, results, and `work/` until it expires after 14 days.

To confirm nothing is running:

```bash
aws ec2 describe-instances --profile programmable-bio --region ap-south-1 \
  --filters Name=tag:project,Values=panbiome-gut-ont Name=instance-state-name,Values=pending,running \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,LaunchTime]' --output text
```

The account's running on-demand vCPU quota was 32 (checked 2026-10-30), shared by both compute environments. The X-family quota (1 TB memory machines) was 0, which is why the full 644 GB Kraken2 database is not used here.

## Requirements on the launching machine

- AWS CLI v2 signed in: `aws sso login --profile programmable-bio`. Run locally, `run.sh` exports the session's temporary keys for Nextflow, so the run stops when the SSO session expires (about an hour). For anything longer, set `PANBIOME_REMOTE=1`: `run.sh` uploads this folder to `s3://BUCKET/launch/<run-name>/` and submits Nextflow as a `panbiome-nextflow-head` job on `panbiome-ondemand`, which uses its own IAM role. Its log is in CloudWatch (`/aws/batch/job`) and is copied to `s3://BUCKET/launch/<run-name>/nextflow.log` at the end.
- Batch instances install the AWS CLI (conda-forge `awscli` 2.38.3, Python 3.12) from an explicit package list in the launch template. The conda build carries its own zlib, which the Flye image lacks, and the explicit list avoids the solver, which ran out of memory on 4 GB instances.
- Nextflow 26.x. Nextflow 23.10 can no longer download the `nf-amazon` plugin. `run.sh` uses `~/.nextflow/launcher/nextflow` (the 26.10.4 launcher from the Nextflow GitHub release) unless `NEXTFLOW` is set.

## Commands

```bash
# Deploy or update the stack (Mumbai default VPC). Update only when no run is active: a launch template change
# rolls the task machines, and a run whose machines are replaced cannot be resumed.
aws cloudformation deploy --profile programmable-bio --region ap-south-1 \
  --stack-name panbiome-gut-ont-batch --template-file infra/aws/batch.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides VpcId=VPC_ID SubnetIds=SUBNET_A,SUBNET_B,SUBNET_C

# Mirror the core image (once per tag)
aws ecr get-login-password --profile programmable-bio --region ap-south-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com
docker tag ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0 ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/panbiome-gut-ont-core:0.1.0
docker push ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/panbiome-gut-ont-core:0.1.0

# Stub run on Batch
PANBIOME_PROFILE=awsbatch,test infra/aws/run.sh stub-test -stub-run \
  --fastq test_data/fastq_pass --sample_sheet test_data/sample_sheet.csv \
  --host_ref test_data/stub_db/host.mmi --kraken2_db test_data/stub_db/kraken2

# Databases (long, so run Nextflow on Batch)
PANBIOME_REMOTE=1 PANBIOME_SCRIPT=infra/aws/fetch_dbs.nf infra/aws/run.sh fetch-dbs --db_dir s3://BUCKET/db
PANBIOME_REMOTE=1 PANBIOME_SCRIPT=infra/aws/build_kraken2.nf infra/aws/run.sh build-kraken2 --db_dir s3://BUCKET/db
```

## Watching a run

The run monitor ([MONITOR.md](MONITOR.md)) shows the same information in a browser. From a terminal, with `export AWS_PROFILE=programmable-bio AWS_REGION=ap-south-1`:

```bash
# Status of a head job (run.sh prints its ID when it submits)
aws batch describe-jobs --jobs HEAD_JOB_ID --query 'jobs[].[jobName,status,statusReason]' --output table

# Follow the Nextflow log of a head job
aws logs tail /aws/batch/job --follow --log-stream-names "$(aws batch describe-jobs --jobs HEAD_JOB_ID --query 'jobs[0].container.logStreamName' --output text)"

# Tasks queued, starting or running in all queues
for q in panbiome-default panbiome-ondemand panbiome-build; do for s in RUNNABLE STARTING RUNNING; do aws batch list-jobs --job-queue $q --job-status $s --query 'jobSummaryList[].[jobName,status]' --output text; done; done

# Per-task time and peak memory once the run has ended
aws s3 cp s3://BUCKET/results/RUN/execution/trace.txt - | column -t -s $'\t'
```

A task's `.command.log` and `.command.err` reach its S3 work directory only when the task ends.

## Databases, caching and transfers

For `main.nf`, `run.sh` presets every database under `s3://BUCKET/db/` ([infra/aws/databases.config](../infra/aws/databases.config)), with `--kraken2_confidence 0.005` for the 64 GB Kraken2 build. A run needs only `--fastq` and `--sample_sheet`; any `--param` on the command line overrides the preset, and `PANBIOME_DB_PRESET=0` turns it off.

The `awsbatch` profile sets `--db_cache true`. Each task machine then keeps one copy of every database it has used in `/mnt/dbcache` on its own disk ([bin/dbcache](../bin/dbcache)). The first task that needs a database downloads it with the AWS CLI's CRT transfer client; tasks that start meanwhile wait for that download, and later tasks on the same machine use the copy without any transfer. Without the cache, every Kraken2, eggNOG, CheckM2, geNomad, sylph, AMRFinderPlus and host-depletion task copied its database from S3 again. Nextflow copies other task inputs and outputs 16 at a time (`aws.batch.maxParallelTransfers`).

Tool images from quay.io are pulled through an ECR pull-through cache (`QuayPullThroughCache` in `batch.yaml`): the first pull copies an image into ECR in `ap-south-1`, later machines pull it from there. `run.sh` switches the `container_*` parameters to `ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/quay/...` only once the rule exists.

## Resuming a run

Remote runs keep Nextflow's task cache in `s3://BUCKET/cache/<session-id>/` while they run (Nextflow's cloud cache, `NXF_CLOUDCACHE_PATH`), and `run.sh` saves the session id to `s3://BUCKET/launch/<run-name>/session-id`. To rerun a failed or cancelled run and reuse every task that succeeded, launch it again with the same run name plus `PANBIOME_RESUME=1`:

```bash
PANBIOME_REMOTE=1 PANBIOME_RESUME=1 infra/aws/run.sh zymo-fecal1 <same arguments as before>
```

Because the cache is written as tasks finish, this works even when the head machine was terminated mid-run. The head job itself is submitted with a retry: if its machine goes away (`Host EC2 ... terminated`), Batch starts it once more and it resumes on its own. A run that fails for any other reason is not retried. Task work directories expire with `work/` after 14 days, so resume only works within that window.

Runs launched on 2026-10-31 before the cloud cache saved their cache to `s3://BUCKET/launch/<run-name>/.nextflow/` when they ended; `PANBIOME_RESUME=1` still resumes those. Earlier runs cannot be resumed.

## Chaining runs

`PANBIOME_AFTER="JOB_ID [JOB_ID...]"` submits the head job held in `PENDING` until those Batch jobs succeed. If any of them fails, Batch fails the held job too, so nothing starts on a broken database. No machine runs while a job waits, and nothing polls.

```bash
# Fecal reference run, started automatically once its reads have been fetched
PANBIOME_REMOTE=1 PANBIOME_AFTER="FETCH_HEAD_JOB_ID" infra/aws/run.sh zymo-fecal1 \
  --fastq s3://BUCKET/test_data/zymo_fecal/fastq_pass --sample_sheet s3://BUCKET/test_data/zymo_fecal/sample_sheet.csv
```

Results go to `s3://BUCKET/results/<run-name>/` and the work directory to `s3://BUCKET/work/<run-name>/`. Deleting the stack keeps the bucket.
