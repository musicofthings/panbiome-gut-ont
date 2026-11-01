# Roadmap

Status on 2026-10-30: the workflow runs on AWS Batch (`ap-south-1`, on-demand only, scales to zero; see [AWS.md](AWS.md)). The AWS stub run passed 48/48 tasks. Six databases are in S3 and the 64 GB GTDB r226 Kraken2 + Bracken database is being built. No real sample has been run on AWS yet.

## Phase A: first real run on AWS (next)

1. Finish `build_kraken2.nf` and check `db/k2_gtdb_r226_64GB` (`kraken2-inspect`, Bracken `database1000mers.kmer_distrib` present).
2. Run one real sample end to end with `PANBIOME_REMOTE=1`, all database paths on S3. Queued as `zymo-aws1` (first ~3 Gb of the public ZymoBIOMICS mock run ERR2906227). The Kraken2 build succeeded. Resubmitted on 2026-10-31 behind a new read download from NCBI's SRA copy on AWS, because ENA was too slow. Also queued on 2026-10-31: `zymo-fecal1`, the first ~3 Gb of the ZymoBIOMICS Fecal Reference D6323 (EPI2ME `zymo_fecal_2025.05`, R10.4.1 SUP 5.0.0), which is the dataset to use from now on; see "Chaining runs" in [AWS.md](AWS.md). This is the first real-data run of SemiBin2, CheckM2, AMRFinderPlus, geNomad and eggNOG.
   - Done: `zymo-fecal1` succeeded on 2026-10-31 in 4 h 14 min (172 bins, 9 high quality; 273 species by both methods at Kraken2 confidence 0.05). `zymo-fecal2` on the faster code succeeded on 2026-11-01 in 3 h 13 min with identical read counts and host depletion (301 host reads of 469,645): ingest 12 min → 48 s, filter 12 min → 12 s, host depletion 44 min → 2 min 42 s, Flye 73 → 37 min. 316 species by both methods at confidence 0.005; 173 bins, 8 high quality. Slower: Medaka 56 → 70 min on the less polished Flye draft, and eggNOG 40 → 66 min (its own time 2,429 → 3,617 s), which led to the CRT downloads and `--eggnog_dbmem`.
3. Record peak memory and wall time per process from the trace, then set `big_memory` and per-process limits from those numbers.
4. Record the cost of that run (Cost Explorer, tag `project=panbiome-gut-ont`).

## Phase B: web frontend

Goal: a lab user signs in, uploads a run's FASTQ and sample sheet, starts the workflow, follows progress, and opens the reports, without the AWS CLI or Nextflow.

### Proposed architecture (pay per use, nothing idle)

| Piece | Choice | Why |
| --- | --- | --- |
| Frontend | React + Vite, static build on S3 + CloudFront (or Cloudflare Pages) | No server to keep running. |
| API | FastAPI on Lambda (Mangum adapter) behind API Gateway HTTP API, routes under `/api/...` | Matches the workspace's FastAPI convention; no cost while idle. |
| Sign-in | Amazon Cognito user pool, JWT authorizer on API Gateway | Patient metadata is in the sample sheet, so every route needs sign-in. |
| Uploads | Browser uploads straight to S3 with presigned multipart URLs (`uploads/<run>/`) | 3 to 4 Gb per sample is too large for API Gateway or Lambda. |
| Launch | API calls `batch:SubmitJob` with the existing `panbiome-nextflow-head` job definition, the same command `run.sh` builds with `PANBIOME_REMOTE=1` | Reuses what is already tested. |
| Run records | DynamoDB on-demand table: run id, user, sample sheet, params, head job id, status, timestamps | Pay per request. |
| Progress | Nextflow `-with-weblog https://<api>/api/runs/<id>/events` posting task events to the API, plus head job state from Batch | Live per-task progress without polling S3. |
| Reports | API returns short-lived presigned GET URLs for `results/<run>/wf-gut-report.html` and the per-sample reports | Bucket stays private. |

Screens: sign in; runs list (status, samples, start time, cost estimate); new run (upload, sample sheet check using the same rules as `validate_samplesheet`, database preset, options from `nextflow_schema.json`); run detail (task progress, logs, cancel); reports.

Rules carried over from the workspace conventions: the frontend calls the API only with relative `/api/...` paths; the Vite dev server proxies `/api` to the local FastAPI; the API sets CORS explicitly (`http://localhost:5173` and `http://127.0.0.1:5173` in development, `ALLOWED_ORIGINS` from the environment in production, never `*`); `.env.example` lists `ALLOWED_ORIGINS` and the API base settings. Light theme only.

Decided on 2026-10-31:

- Build our own app rather than use Seqera Platform. The first part is a read-only run monitor; upload and launch come next.
- Only Panbiome lab staff sign in (an invite-only Cognito user pool). Sample data stays in `ap-south-1`.
- The frontend is hosted on S3 + CloudFront in `ap-south-1`, in the same account as the data.

Status:

1. Run monitor: built for local use ([MONITOR.md](MONITOR.md)). It lists runs and shows the step graph with per-sample task status, logs, parameters and reports. Status comes from AWS Batch while a run is going and from `trace.txt` once it has finished, with no change to the workflow. Not yet deployed and has no sign-in.
2. Hosting: `infra/aws/web.yaml` and `infra/aws/deploy_web.sh` (Cognito invite-only user pool with TOTP MFA, the API on Lambda behind an HTTP API with a JWT authorizer, the site on S3 + CloudFront). Written on 2026-10-31, not deployed yet.
3. Then: upload (presigned multipart), launch through the head job definition, DynamoDB run records, cancel, and cost per run. Live progress may move to Nextflow `-with-weblog` once the API is public; until then, Batch is polled every 15 seconds.

## Phase C: EPI2ME integration

Goal: lab staff start the workflow from the EPI2ME desktop app next to the sequencer, as they do for ONT's own workflows.

1. Import `musicofthings/panbiome-gut-ont` in EPI2ME (Workflows > Import workflow > Import from GitHub) and check that the settings form renders from `nextflow_schema.json`. Not yet done: the app is not installed on the development machine.
2. Check the repository against the conventions of ONT's `epi2me-labs` workflows (schema groups, input selectors, output definitions) and fix what the import shows.
3. Decide where compute runs when started from EPI2ME:
   - Local: the sequencing PC needs the databases (about 145 GB with the 64 GB Kraken2 build) and enough memory for Kraken2 (about 80 GB).
   - AWS: EPI2ME starts the run with the `awsbatch` profile. Check which Nextflow version EPI2ME bundles; the `awsbatch` profile needs Nextflow 26.x because older launchers can no longer fetch the `nf-amazon` plugin. Credentials on the sequencing PC must be a narrow role, not an administrator login.
   - Split: QC and host depletion locally (human reads never leave the site), the rest on AWS.
4. If both the web frontend and EPI2ME are used, both should launch through the same head job definition so runs land in the same S3 layout and appear in the same runs list.
