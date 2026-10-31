#!/usr/bin/env bash
# Deploy the run monitor: package api/ for Lambda, deploy infra/aws/web.yaml, then build web/ and upload it.
#   infra/aws/deploy_web.sh
# Run it again after changing api/ or web/. The first deploy creates the Cognito user pool; add staff with
#   aws cognito-idp admin-create-user --user-pool-id POOL_ID --username EMAIL \
#     --user-attributes Name=email,Value=EMAIL Name=email_verified,Value=true --desired-delivery-mediums EMAIL
set -euo pipefail
cd "$(dirname "$0")/../.."

export AWS_PROFILE=${AWS_PROFILE:-programmable-bio}
export AWS_REGION=${AWS_REGION:-ap-south-1}
batch_stack=${PANBIOME_STACK:-panbiome-gut-ont-batch}
web_stack=${PANBIOME_WEB_STACK:-panbiome-gut-ont-web}

output() {
  aws cloudformation describe-stacks --stack-name "$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text
}
bucket=$(output "$batch_stack" Bucket)
account=$(aws sts get-caller-identity --query Account --output text)
auth_prefix=${PANBIOME_AUTH_PREFIX:-panbiome-$account}

build=$(mktemp -d -t panbiome-web)
trap 'rm -r "$build"' EXIT

# Lambda runs Python 3.12 on arm64, so fetch wheels for that platform rather than the laptop's.
python3 -m pip install --quiet --no-warn-conflicts --target "$build/lambda" --platform manylinux2014_aarch64 \
  --implementation cp --python-version 3.12 --only-binary=:all: \
  fastapi==0.162.0 mangum==0.22.0 boto3==1.43.123
cp -R api/panbiome_api "$build/lambda/"
find "$build/lambda" -name '__pycache__' -prune -exec rm -r {} +
(cd "$build/lambda" && zip -qrX "$build/api.zip" .)
code_key="deploy/monitor-api-$(shasum -a 256 "$build/api.zip" | cut -c1-16).zip"
aws s3 cp "$build/api.zip" "s3://$bucket/$code_key" --only-show-errors

aws cloudformation deploy --stack-name "$web_stack" --template-file infra/aws/web.yaml \
  --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset --tags project=panbiome-gut-ont \
  --parameter-overrides DataBucket="$bucket" CodeKey="$code_key" AuthDomainPrefix="$auth_prefix"

site_bucket=$(output "$web_stack" SiteBucket)
printf '{"authDomain":"%s","clientId":"%s"}\n' "$(output "$web_stack" AuthDomain)" "$(output "$web_stack" ClientId)" \
  > "$build/config.json"

(cd web && npm ci --silent && npm run build)
# Hashed assets never change; index.html and config.json must be fetched fresh after each deploy.
aws s3 sync web/dist/assets "s3://$site_bucket/assets" --delete --only-show-errors \
  --cache-control 'public, max-age=31536000, immutable'
aws s3 sync web/dist "s3://$site_bucket" --delete --only-show-errors --exclude 'assets/*' --cache-control 'no-cache'
aws s3 cp "$build/config.json" "s3://$site_bucket/config.json" --only-show-errors \
  --cache-control 'no-cache' --content-type application/json
aws cloudfront create-invalidation --distribution-id "$(output "$web_stack" DistributionId)" --paths '/*' \
  --query Invalidation.Id --output text >/dev/null

echo "Site:      $(output "$web_stack" SiteUrl)"
echo "User pool: $(output "$web_stack" UserPoolId)"
