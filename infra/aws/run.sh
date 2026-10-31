#!/usr/bin/env bash
# Run the workflow on AWS Batch using the outputs of the panbiome-gut-ont-batch stack.
#   infra/aws/run.sh <run-name> [nextflow args...]
#   PANBIOME_PROFILE=awsbatch,test infra/aws/run.sh stub-test -stub-run --fastq ... --sample_sheet ...
#   PANBIOME_SCRIPT=infra/aws/fetch_dbs.nf infra/aws/run.sh fetch-dbs --db_dir s3://BUCKET/db
# Paths under s3://$BUCKET/ can be passed directly as --fastq, --kraken2_db, and so on. For main.nf the
# databases under s3://$BUCKET/db are preset (infra/aws/databases.config); PANBIOME_DB_PRESET=0 turns that off.
#
# PANBIOME_REMOTE=1 uploads this folder to s3://$BUCKET/launch/<run-name>/ and runs Nextflow itself as a
# Batch job on panbiome-ondemand, so the run does not stop when the laptop or the SSO session does.
# Its log goes to CloudWatch (/aws/batch/job) and to s3://$BUCKET/launch/<run-name>/nextflow.log.
# PANBIOME_AFTER="JOB_ID [JOB_ID...]" holds that head job until those Batch jobs succeed; if one fails, so does it.
#
# Remote runs keep Nextflow's task cache in s3://$BUCKET/cache/<session-id>/ as they go (cloud cache), so a
# run can be resumed even when its head machine was lost. PANBIOME_RESUME=1 with the same run name reuses
# every task that already succeeded. If the head machine is terminated, Batch retries the head job once and
# it resumes by itself.
set -euo pipefail
cd "$(dirname "$0")/../.."

run_name=${1:?usage: infra/aws/run.sh <run-name> [nextflow args...]}
shift

export AWS_PROFILE=${AWS_PROFILE:-programmable-bio}
export AWS_REGION=${AWS_REGION:-ap-south-1}
stack=${PANBIOME_STACK:-panbiome-gut-ont-batch}
script=${PANBIOME_SCRIPT:-main.nf}

output() {
  aws cloudformation describe-stacks --stack-name "$stack" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
bucket=$(output Bucket)
job_role=$(output JobRoleArn)
core_image=$(output CoreImageUri)

nf_args=(run "$script" -profile "${PANBIOME_PROFILE:-awsbatch}" -c aws-run.config
  -work-dir "s3://$bucket/work/$run_name"
  --out_dir "s3://$bucket/results/$run_name"
  --container_core "$core_image:0.1.0")
# Tool images from quay.io come through the stack's ECR pull-through cache once it is deployed.
if aws ecr describe-pull-through-cache-rules --ecr-repository-prefixes quay >/dev/null 2>&1; then
  while read -r name image; do
    nf_args+=(--"$name" "${core_image%%/*}/quay/$image")
  done < <(sed -nE "s/^[[:space:]]*(container_[a-z0-9_]+)[[:space:]]*=[[:space:]]*'quay\.io\/([^']+)'.*/\1 \2/p" nextflow.config)
fi
nf_args+=("$@")

write_config() {
  printf "aws.batch.jobRole = '%s'\n" "$job_role" > "$1"
  if [[ "$script" == main.nf && "${PANBIOME_DB_PRESET:-1}" == 1 ]]; then
    printf "params.db_root = 's3://%s/db'\n" "$bucket" >> "$1"
    cat infra/aws/databases.config >> "$1"
  fi
}

if [[ "${PANBIOME_REMOTE:-0}" == 1 ]]; then
  launch="s3://$bucket/launch/$run_name"
  staging=$(mktemp -d -t panbiome-launch)
  trap 'rm -r "$staging"' EXIT

  env_vars="export NXF_CLOUDCACHE_PATH=s3://$bucket/cache NXF_IGNORE_RESUME_HISTORY=true"
  if [[ "${PANBIOME_RESUME:-0}" == 1 ]] && session=$(aws s3 cp "$launch/session-id" - 2>/dev/null); then
    :
  elif [[ "${PANBIOME_RESUME:-0}" == 1 ]] && aws s3 ls "$launch/.nextflow/cache/" >/dev/null 2>&1; then
    # Launched before the cloud cache: the head job left its .nextflow folder in the launch folder
    session=""
    env_vars="true"
    nf_args+=(-resume)
  elif [[ "${PANBIOME_RESUME:-0}" == 1 ]]; then
    echo "No saved session for $run_name, so there is nothing to resume." >&2
    exit 1
  else
    session=$(uuidgen | tr '[:upper:]' '[:lower:]')
  fi
  name_arg=""
  if [[ -n "$session" ]]; then
    # Nextflow run names are lowercase and start with a letter
    base=$(printf '%s' "$run_name" | tr '[:upper:]._' '[:lower:]--')
    [[ "$base" =~ ^[a-z] ]] || base="run-$base"
    nf_args+=(-resume "$session")
    # Each Batch attempt of the head job gets its own run name
    name_arg=" -name $base-$(date -u +%Y%m%d%H%M%S)-a\${AWS_BATCH_JOB_ATTEMPT:-1}"
  fi

  write_config "$staging/aws-run.config"
  # The CLI checks symlinks even under excluded folders and fails on broken ones left in work/.
  aws s3 sync . "$launch/" --only-show-errors --no-follow-symlinks \
    --exclude '.git/*' --exclude '.claude/*' --exclude 'work/*' --exclude '.nextflow*' \
    --exclude 'output/*' --exclude 'stub_output*' --exclude '*.DS_Store' --exclude 'api_docs.md' \
    --exclude 'api/*' --exclude 'web/*'
  aws s3 cp "$staging/aws-run.config" "$launch/aws-run.config" --only-show-errors
  if [[ -n "$session" ]]; then
    printf '%s' "$session" | aws s3 cp - "$launch/session-id" --only-show-errors
  fi

  cmd="$env_vars && mkdir -p /launch && cd /launch && /opt/aws-cli/bin/aws s3 sync $launch/ . --only-show-errors"
  cmd+=" && { nextflow $(printf '%q ' "${nf_args[@]}")$name_arg; rc=\$?; }"
  cmd+="; /opt/aws-cli/bin/aws s3 cp .nextflow.log $launch/nextflow.log --only-show-errors; exit \${rc:-1}"
  python3 -c 'import json,sys; print(json.dumps({"command": ["bash", "-c", sys.argv[1]]}))' "$cmd" > "$staging/overrides.json"

  after=(); for id in ${PANBIOME_AFTER:-}; do after+=("jobId=$id"); done
  if (( ${#after[@]} )); then after=(--depends-on "${after[@]}"); fi
  # Retry only when the head machine itself went away (stack update, hardware); a failed run is not retried
  retry='{"attempts":2,"evaluateOnExit":[{"onStatusReason":"Host EC2*","action":"RETRY"},{"onReason":"*","action":"EXIT"}]}'
  aws batch submit-job --job-name "panbiome-head-$run_name" --job-queue panbiome-ondemand \
    --job-definition "$(output HeadJobDefinition)" ${after[@]+"${after[@]}"} \
    --container-overrides "file://$staging/overrides.json" --retry-strategy "$retry" \
    --query '[jobName,jobId]' --output text
  exit 0
fi

# Nextflow's AWS SDK cannot read sso-session profiles, so hand it the session's temporary keys.
if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  eval "$(aws configure export-credentials --format env)"
fi
if [[ "${PANBIOME_RESUME:-0}" == 1 ]]; then nf_args+=(-resume); fi

write_config aws-run.config
trap 'rm -f aws-run.config' EXIT

# Nextflow 23.10 can no longer download nf-amazon, and its launcher cannot switch to 26.x with NXF_VER.
# Default to the 26.10.4 launcher from github.com/nextflow-io/nextflow/releases, saved under ~/.nextflow/launcher.
"${NEXTFLOW:-$HOME/.nextflow/launcher/nextflow}" "${nf_args[@]}"
