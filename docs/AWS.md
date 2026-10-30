# Running on AWS Batch

Databases live in S3 and tasks run on AWS Batch in `ap-south-1`. Nothing large is stored on the launching machine.

## Pieces

| File | What |
| --- | --- |
| `infra/aws/batch.yaml` | CloudFormation stack: private encrypted S3 bucket (`work/` expires after 14 days), ECR repository for the core image, IAM roles, and three job queues. |
| `infra/aws/run.sh` | Launches any of the workflows with the stack's bucket, job role and ECR image. |
| `infra/aws/fetch_dbs.nf` | Downloads sylph r226 + lineage map, CheckM2, geNomad, AMRFinderPlus, eggNOG 5.0.2 and the T2T-CHM13 minimap2 index into `s3://BUCKET/db/`. |
| `infra/aws/build_kraken2.nf` | Builds the 64 GB GTDB r226 Kraken2 + Bracken database into `s3://BUCKET/db/k2_gtdb_r226_64GB`. |

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
# Deploy or update the stack (Mumbai default VPC)
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

Results go to `s3://BUCKET/results/<run-name>/` and the work directory to `s3://BUCKET/work/<run-name>/`. Deleting the stack keeps the bucket.
