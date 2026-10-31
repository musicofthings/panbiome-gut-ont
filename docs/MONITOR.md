# Run monitor

A read-only web app for following workflow runs on AWS Batch. It lists the runs, shows the pipeline's steps as a graph with each step's status and per-sample tasks, and gives access to the Nextflow log, task logs, parameters and reports. It cannot upload data, start runs or cancel them. Those features come in the next part of Phase B (see [ROADMAP.md](ROADMAP.md)).

| Folder | What |
| --- | --- |
| `api/` | FastAPI app (`panbiome_api`). Read-only access to AWS Batch, S3 and CloudWatch Logs. Routes are under `/api/...`. |
| `web/` | React + Vite app. It calls the API only through relative `/api/...` paths. |

## Where the status comes from

The pipeline needs no changes for the monitor to work.

- **Runs** are the folders under `s3://BUCKET/launch/` and `s3://BUCKET/results/`. The latest `panbiome-head-<run>` job on `panbiome-ondemand` gives a run's status, its times and the script it runs (`main.nf` or a database or test-data workflow).
- **Live tasks** come from AWS Batch. The API lists jobs in the three task queues created after the head job, and keeps those whose command reads `.command.run` from `work/<run>/`. Each task's latest attempt counts.
- **Finished runs** use `results/<run>/execution/trace.txt`, but only if that file is newer than the latest head job, because a rerun with the same name overwrites it. The trace includes peak memory per task, which Batch does not report.
- **Which steps belong to a run** comes from `results/<run>/execution/params.json`, using the same rules as `main.nf` (assay, `skip_*` flags, which databases are set). Steps a run's params turn off are hidden unless "Show steps not in this run" is ticked. Until the run writes `params.json`, every step is shown as not started.
- **Task logs** are `.command.sh`, `.command.err` and `.command.log` in the task's S3 work directory. Batch copies the last two there only when the task ends.
- **Reports** are the `.html` files under `results/<run>/`, opened through presigned links that expire after 15 minutes. The bucket stays private.

AWS Batch keeps finished jobs for about 7 days. After that a run's status and tasks come only from its trace, and the Nextflow log tab is empty.

Status shown for a step: failed if any of its tasks failed, otherwise running if any task is running or only some are done, otherwise queued, otherwise done. A step with no tasks is not started.

## Run it locally

Needs Python 3.11+, Node 20+, and an SSO login that can read the stack's bucket, Batch queues and logs.

```bash
aws sso login --profile programmable-bio
```

```bash
cd api && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && cp .env.example .env
```

Set `PANBIOME_BUCKET` in `api/.env` to the stack's `Bucket` output. `PANBIOME_REGION` is set explicitly because boto3 ignores `AWS_REGION`, and the `programmable-bio` profile's default region is `ap-south-2`.

```bash
cd api && .venv/bin/uvicorn panbiome_api.main:app --reload --env-file .env --port 8000
```

```bash
cd web && npm install && cp .env.example .env && npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to `API_PROXY_TARGET` (default `http://127.0.0.1:8000`).

Tests and lint:

```bash
cd api && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -v
```

```bash
cd web && npm run build && npm run lint
```

## CORS

The API sets CORS explicitly. With `PANBIOME_ENV=development` and `ALLOWED_ORIGINS` empty, it allows `http://localhost:5173` and `http://127.0.0.1:5173` (port from `WEB_DEV_PORT`). With `PANBIOME_ENV=production`, `ALLOWED_ORIGINS` is required and is never `*`. Requests carry no cookies (sign-in will use a bearer token), so credentials are not allowed. Only `GET` is allowed.

```
CORS smoke-test (Chrome DevTools):
  Console tab → paste:
    fetch('/api/health').then(r => r.json()).then(console.log)
  Expected: JSON response, no CORS error in console.

  Network tab → select the /api request → Headers:
    Request  — Origin: http://localhost:5173
    Response — Access-Control-Allow-Origin: http://localhost:5173
```

Through the Vite proxy the browser sees one origin, so this test passes without CORS headers. To exercise the API's own CORS, call it directly: `curl -i -H 'Origin: http://localhost:5173' http://127.0.0.1:8000/api/health`.

## Hosting on AWS

`infra/aws/web.yaml` is a separate CloudFormation stack (`panbiome-gut-ont-web`) next to the Batch stack:

| Piece | What |
| --- | --- |
| Cognito user pool `panbiome-staff` | Invite-only: only an administrator can create accounts. Sign-in by email, password of at least 12 characters, TOTP MFA required. Managed login (v2) on `panbiome-<account>.auth.ap-south-1.amazoncognito.com`. |
| App client `panbiome-monitor-web` | Public client with no secret, authorization code grant with PKCE, scopes `openid email`. Access and ID tokens last 60 minutes, refresh tokens 12 hours, with revocation on sign-out. |
| API | `panbiome_api.lambda_handler` (FastAPI through Mangum) on Lambda, Python 3.12 arm64, behind an HTTP API. One route, `GET /api/{proxy+}`, with a JWT authorizer that requires an access token from the app client. The Lambda role can only list and read `launch/`, `results/` and `work/` in the data bucket, list and describe Batch jobs, and read `/aws/batch/job` logs. Access logs record the user's email. |
| Site | Private S3 bucket behind CloudFront (origin access control). `/api/*` goes to the HTTP API on the same host, so the browser needs no CORS. A CloudFront function serves `index.html` for client-side routes. Responses carry a strict Content-Security-Policy, HSTS, `X-Frame-Options: DENY` and `nosniff`. |

The browser keeps its tokens in `sessionStorage`, so they end with the tab. `/config.json` (the Cognito domain and client id) is written by the deploy script; without it, as under `npm run dev`, sign-in is off.

Deploy or update, after `aws sso login --profile programmable-bio`:

```bash
infra/aws/deploy_web.sh
```

It packages `api/` for Lambda (arm64 wheels), uploads the zip to `s3://BUCKET/deploy/`, deploys the stack, builds `web/`, uploads it with `config.json`, and prints the site URL and user pool id. Add a staff member (Cognito emails a temporary password; MFA is set up at first sign-in):

```bash
aws cognito-idp admin-create-user --profile programmable-bio --region ap-south-1 --user-pool-id POOL_ID --username EMAIL --user-attributes Name=email,Value=EMAIL Name=email_verified,Value=true --desired-delivery-mediums EMAIL
```

The user pool has deletion protection on; deleting the stack fails until it is turned off.

## Not built yet

- Upload, launch and cancel; DynamoDB run records; a cost per run.
