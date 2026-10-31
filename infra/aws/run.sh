#!/usr/bin/env bash
# Run the workflow on AWS Batch using the outputs of the panbiome-gut-ont-batch stack.
#   infra/aws/run.sh <run-name> [nextflow args...]
#   PANBIOME_PROFILE=awsbatch,test infra/aws/run.sh stub-test -stub-run --fastq ... --sample_sheet ...
#   PANBIOME_SCRIPT=infra/aws/fetch_dbs.nf infra/aws/run.sh fetch-dbs --db_dir s3://BUCKET/db
# Paths under s3://$BUCKET/ can be passed directly as --fastq, --kraken2_db, and so on.
#
# PANBIOME_REMOTE=1 uploads this folder to s3://$BUCKET/launch/<run-name>/ and runs Nextflow itself as a
# Batch job on panbiome-ondemand, so the run does not stop when the laptop or the SSO session does.
# Its log goes to CloudWatch (/aws/batch/job) and to s3://$BUCKET/launch/<run-name>/nextflow.log.
# PANBIOME_AFTER="JOB_ID [JOB_ID...]" holds that head job until those Batch jobs succeed; if one fails, so does it.
set -euo pipefail
cd "$(dirname "$0")/../.."

run_name=${1:?usage: infra/aws/run.sh <run-name> [nextflow args...]}
shift

export AWS_PROFILE=${AWS_PROFILE:-programmable-bio}
export AWS_REGION=${AWS_REGION:-ap-south-1}
stack=${PANBIOME_STACK:-panbiome-gut-ont-batch}

output() {
  aws cloudformation describe-stacks --stack-name "$stack" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
bucket=$(output Bucket)
job_role=$(output JobRoleArn)
core_image=$(output CoreImageUri)

nf_args=(run "${PANBIOME_SCRIPT:-main.nf}" -profile "${PANBIOME_PROFILE:-awsbatch}" -c aws-run.config
  -work-dir "s3://$bucket/work/$run_name"
  --out_dir "s3://$bucket/results/$run_name"
  --container_core "$core_image:0.1.0"
  "$@")

if [[ "${PANBIOME_REMOTE:-0}" == 1 ]]; then
  launch="s3://$bucket/launch/$run_name"
  staging=$(mktemp -d -t panbiome-launch)
  trap 'rm -r "$staging"' EXIT
  printf "aws.batch.jobRole = '%s'\n" "$job_role" > "$staging/aws-run.config"
  # The CLI checks symlinks even under excluded folders and fails on broken ones left in work/.
  aws s3 sync . "$launch/" --only-show-errors --no-follow-symlinks \
    --exclude '.git/*' --exclude '.claude/*' --exclude 'work/*' --exclude '.nextflow*' \
    --exclude 'output/*' --exclude 'stub_output*' --exclude '*.DS_Store' --exclude 'api_docs.md'
  aws s3 cp "$staging/aws-run.config" "$launch/aws-run.config" --only-show-errors

  cmd="mkdir -p /launch && cd /launch && /opt/aws-cli/bin/aws s3 sync $launch/ . --only-show-errors"
  cmd+=" && { nextflow $(printf '%q ' "${nf_args[@]}"); rc=\$?; }"
  cmd+="; /opt/aws-cli/bin/aws s3 cp .nextflow.log $launch/nextflow.log --only-show-errors; exit \${rc:-1}"
  python3 -c 'import json,sys; print(json.dumps({"command": ["bash", "-c", sys.argv[1]]}))' "$cmd" > "$staging/overrides.json"

  after=(); for id in ${PANBIOME_AFTER:-}; do after+=("jobId=$id"); done
  if (( ${#after[@]} )); then after=(--depends-on "${after[@]}"); fi
  aws batch submit-job --job-name "panbiome-head-$run_name" --job-queue panbiome-ondemand \
    --job-definition "$(output HeadJobDefinition)" ${after[@]+"${after[@]}"} \
    --container-overrides "file://$staging/overrides.json" \
    --query '[jobName,jobId]' --output text
  exit 0
fi

# Nextflow's AWS SDK cannot read sso-session profiles, so hand it the session's temporary keys.
if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  eval "$(aws configure export-credentials --format env)"
fi

printf "aws.batch.jobRole = '%s'\n" "$job_role" > aws-run.config
trap 'rm -f aws-run.config' EXIT

# Nextflow 23.10 can no longer download nf-amazon, and its launcher cannot switch to 26.x with NXF_VER.
# Default to the 26.10.4 launcher from github.com/nextflow-io/nextflow/releases, saved under ~/.nextflow/launcher.
"${NEXTFLOW:-$HOME/.nextflow/launcher/nextflow}" "${nf_args[@]}"
