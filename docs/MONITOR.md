# Run monitor

A web app for the pipeline on AWS, like the EPI2ME desktop app but in the cloud:

- **Runs**: the runs on AWS Batch, the pipeline's steps as a graph with each step's status and per-sample tasks, the Nextflow log, task logs and parameters.
- **Report**: QC and results per sample, read from the files a run writes (see "Report viewer" below).
- **Files**: browse the data bucket, upload raw reads and sample sheets to `uploads/`, and download any result.

It cannot start or cancel runs yet (see [ROADMAP.md](ROADMAP.md)).

| Folder | What |
| --- | --- |
| `api/` | FastAPI app (`panbiome_api`). Reads AWS Batch, S3 and CloudWatch Logs, and writes only under `uploads/` in the bucket. Routes are under `/api/...`. |
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

## Report viewer

`/runs/<run>/report` builds the report from the files under `results/<run>/`, so it works for any finished run without re-running anything:

| Section | From |
| --- | --- |
| Run QC: status, reads, yield, N50, quality, host fraction and flags per sample; control status | `run/qc_summary.tsv`, `run/controls/control_status.json`, `run/diversity/alpha_diversity.tsv` |
| Reads: counts, yield, N50, quality, human reads removed, adapters; read length and quality histograms, raw or filtered | `qc/<sample>.raw.stats.json`, `.filtered.stats.json`, `.host.json` |
| Species: top 20 bar chart, the watchlist, and a searchable table of kept species with Bracken and sylph values | `taxonomy/<sample>.species.tsv`, `.taxa_summary.json`, `.watchlist.tsv` |
| Diversity: observed species, Shannon, Simpson, evenness | `run/diversity/alpha_diversity.tsv` |
| MAGs: counts by MIMAG quality, completeness against contamination for every bin, bin table | `resistance/<sample>.mags.tsv` |
| Resistance: AMR genes with class, identity, coverage, contig, plasmid and bin | `resistance/<sample>.amr_linked.tsv` (or `.amrfinder.tsv`), `.plasmid_summary.tsv` |
| Function: targeted gut functions and the top KEGG modules | `function/<sample>.function_targets.tsv`, `.function_module.tsv` |

Sections whose files are missing (a skipped step, or a run still going) say so instead of failing. The original HTML reports (sample report, Krona, run report) open from the side panel.

## Files and uploads

The Files page has three areas of the data bucket: **Uploads** (`uploads/`, read and write), **Results** (`results/`) and **Test data** (`test_data/`), both read-only. Folders are browsed with S3 listings; downloads are presigned links valid for an hour.

Uploads go from the browser straight to S3, so files of any size never pass through the API or Lambda:

1. `POST /api/uploads` starts a multipart upload (parts of 16 MiB, larger for files over 160 GB so a file stays under S3's 10,000 parts) and records the signed-in user in the object's `uploaded-by` metadata. An existing file is not replaced unless the user chooses Overwrite.
2. `POST /api/uploads/parts` signs part URLs, 50 at a time, valid for an hour.
3. The browser sends 4 parts at a time per file and 2 files at a time, retrying a part up to 4 times and re-signing it if the URL expired.
4. `POST /api/uploads/complete` joins the parts; on failure or cancel, `POST /api/uploads/abort` discards them. The bucket's lifecycle rule also removes unfinished uploads after 7 days.

Whole run folders can be dropped on the page or picked with "Upload folder"; their relative paths are kept. Uploads keep going while you move to other pages, and the tab asks before closing while one is running. Only empty folders can be deleted.

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

The API sets CORS explicitly. With `PANBIOME_ENV=development` and `ALLOWED_ORIGINS` empty, it allows `http://localhost:5173` and `http://127.0.0.1:5173` (port from `WEB_DEV_PORT`). With `PANBIOME_ENV=production`, `ALLOWED_ORIGINS` is required and is never `*`. Requests carry no cookies (sign-in uses a bearer token), so credentials are not allowed. `GET`, `POST` and `DELETE` are allowed.

Uploads need a second CORS rule, on the **data bucket**, because the browser sends upload parts straight to S3 and must read each part's `ETag`. The Batch stack's `UploadOrigins` parameter sets it: `PUT` from those origins only, with `ETag` exposed. Never `*`. Without it, uploads fail with a network error.

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
| API | `panbiome_api.lambda_handler` (FastAPI through Mangum) on Lambda, Python 3.12 arm64, behind an HTTP API. Routes `GET`, `POST` and `DELETE /api/{proxy+}`, each with a JWT authorizer that requires an access token from the app client. The Lambda role can list and read `launch/`, `results/`, `work/`, `test_data/` and `uploads/` in the data bucket, write and delete only under `uploads/`, list and describe Batch jobs, and read `/aws/batch/job` logs. Presigned links are signed with this role, so they reach nothing else. Access logs record the user's email. |
| Site | Private S3 bucket behind CloudFront (origin access control). `/api/*` goes to the HTTP API on the same host, so the browser needs no CORS. A CloudFront function serves `index.html` for client-side routes. Responses carry a strict Content-Security-Policy (which allows connections to the data bucket's regional S3 endpoint for uploads), HSTS, `X-Frame-Options: DENY` and `nosniff`. |

The browser keeps its tokens in `sessionStorage`, so they end with the tab. `/config.json` (the Cognito domain and client id) is written by the deploy script; without it, as under `npm run dev`, sign-in is off.

Deploy or update, after `aws sso login --profile programmable-bio`:

```bash
infra/aws/deploy_web.sh
```

For uploads, also give the Batch stack the site's origin (and the local dev origins) for the bucket's CORS rule. Do this when no run is active:

```bash
aws cloudformation deploy --profile programmable-bio --region ap-south-1 --stack-name panbiome-gut-ont-batch --template-file infra/aws/batch.yaml --capabilities CAPABILITY_IAM --parameter-overrides UploadOrigins=https://SITE.cloudfront.net,http://localhost:5173,http://127.0.0.1:5173
```

It packages `api/` for Lambda (arm64 wheels), uploads the zip to `s3://BUCKET/deploy/`, deploys the stack, builds `web/`, uploads it with `config.json`, and prints the site URL and user pool id. Add a staff member (Cognito emails a temporary password; MFA is set up at first sign-in):

```bash
aws cognito-idp admin-create-user --profile programmable-bio --region ap-south-1 --user-pool-id POOL_ID --username EMAIL --user-attributes Name=email,Value=EMAIL Name=email_verified,Value=true --desired-delivery-mediums EMAIL
```

The user pool has deletion protection on; deleting the stack fails until it is turned off.

## Not built yet

- Launch and cancel runs from uploaded data; DynamoDB run records; a cost per run.
