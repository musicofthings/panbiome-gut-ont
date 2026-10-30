# Session Handover
_Generated: 2026-10-30T16:25Z (manual /session-sync save)_
_Branch: main · Last commit: e90e98d Queue the first real-data AWS run behind the Kraken2 build._

---

## 🎯 Active Task
**Run panbiome-gut-ont on AWS Batch (ap-south-1) with databases in S3, nothing large on the laptop.**

**Phase:** Roadmap Phase A — first real-data run on AWS (see `docs/ROADMAP.md`).
**Next action:** After `aws sso login --profile programmable-bio`, check the three queued jobs below. When `zymo-aws1` ends, read `s3://panbiome-gut-ont-905663668881-ap-south-1/launch/zymo-aws1/nextflow.log` and `results/zymo-aws1/execution/trace.txt`, then record results in `docs/VALIDATION_LOG.md` and set per-process memory/time from the trace peaks.

---

## 🔄 Jobs in flight (AWS Batch, account 905663668881, profile `programmable-bio`)
| Job | Batch job ID | State at 16:20 UTC | Notes |
|---|---|---|---|
| `panbiome-head-build-kraken2b` | 975b06aa-d537-4b44-af56-1e352689f83d | RUNNING | Task `KRAKEN2_GTDB_R226_CAPPED` 873dcd62-c469-471a-b283-eb37dbd8c9ac on r6i.4xlarge i-09d608705c81d37a8. 137 GB GTDB download done ~15:20 UTC with no resumes; extracting library (~40 MB/s, single-threaded), then kraken2-build (16 threads) and bracken-build. Expected to finish overnight. Output: `db/k2_gtdb_r226_64GB/`. |
| `panbiome-head-fetch-zymo` | 5494417c-d28d-4bd3-94a2-6fe185565bbb | RUNNABLE | Streams first ~3 Gb of ENA ERR2906227 (Zymo mock, R9.4.1) to `test_data/zymo/`. |
| `panbiome-head-zymo-aws1` | b98dcacd-e1cd-40d0-a965-ef343106701b | PENDING | Depends on both jobs above (Batch `dependsOn`); fails automatically if either fails. Full run with all S3 databases, GTDB-Tk off. Results `results/zymo-aws1/`. |

Progress check without SSH: CloudWatch `NetworkIn`/`CPUUtilization` for the instance and EBS `VolumeWriteBytes`; the task's CloudWatch log only prints on download resumes.

---

## ✅ Completed This Session
- CloudFormation stack `panbiome-gut-ont-batch` deployed (user runs deploys; the auto-mode classifier blocks Claude from applying IaC). On-demand only since 2026-10-30 14:20 UTC: spot CE removed, `panbiome-default` and `panbiome-ondemand` share `OnDemandComputeEnv` (MinvCpus 0), `panbiome-build` on `BuildComputeEnv` (1000 GB disk). Head job definition rev 2 has a 72 h timeout (`HeadTimeoutSeconds`).
- Core image mirrored to ECR (`panbiome-gut-ont-core:0.1.0`, same digest as GHCR).
- AWS stub run `stub-test4` passed 48/48.
- Databases in `s3://panbiome-gut-ont-905663668881-ap-south-1/db/` (~79 GB): sylph r226 + map, CheckM2, geNomad, AMRFinderPlus (`amrfinder/latest`), eggNOG 5.0.2, T2T-CHM13 minimap2 index.
- README "Run it on AWS", `docs/AWS.md` (incl. "Chaining runs"), `docs/ROADMAP.md` (Phase A real run, Phase B web frontend, Phase C EPI2ME), CHANGELOG Unreleased.
- Commits pushed to main: cc451c9, e90e98d.

---

## 📋 Remaining Work
1. Phase A: verify Kraken2 DB, review `zymo-aws1`, tune memory/time from trace, record cost (tag `project=panbiome-gut-ont`).
2. Optional: EventBridge → SNS email on head-job completion (needs an email address; user deploys).
3. Phase B web frontend — open decisions in `docs/ROADMAP.md` (who signs in, data residency, CloudFront vs Cloudflare Pages, custom vs Seqera Platform).
4. Phase C EPI2ME — import from GitHub not yet tried; check bundled Nextflow version vs the 26.x needed for `awsbatch`.
5. Laptop cleanup (~30 GB Docker images) — only with explicit approval.
6. X-family quota increase (full 644 GB Kraken2) — user's decision.

---

## 🏗 Architecture Decisions
| Decision | Rationale | Date |
|---|---|---|
| AWS Batch in ap-south-1, on-demand only, scale to zero | User wants no idle cost and no spot interruptions | 2026-10-30 |
| Kraken2 = 64 GB capped GTDB r226 build (Langmead taxonomy/seqid map) | Account has 32 on-demand vCPUs and 0 X-family quota; names still match sylph r226 | 2026-10-30 |
| Long runs use `PANBIOME_REMOTE=1` head jobs | SSO credentials expire in ~1 h | 2026-10-30 |
| Chaining via Batch `dependsOn` (`PANBIOME_AFTER`), not cron | No polling, no laptop, no idle machines | 2026-10-30 |
| Host AWS CLI = conda-forge awscli from explicit lockfile via micromamba | Flye image lacks libz for AWS CLI v2; solver OOM on 4 GB | 2026-10-30 |
| Nextflow 26.10.4 launcher at `~/.nextflow/launcher/nextflow` | 23.10 can no longer fetch nf-amazon | 2026-10-30 |
| Shotgun taxonomy pair is GTDB r226 for Kraken2 and sylph | Reconcile needs shared taxonomy | 2026-10-28 |

---

## ⚠️ Critical Rules
- Never commit secrets, `.env`, or API keys. Leave `api_docs.md` (tool-generated) uncommitted.
- Do not retune `medaka_model`, `bracken_read_len`, `sylph_args`, `min_ani`, or `big_memory` unless asked.
- No downloads >1 GB to the laptop without asking. No `docker push` or git tags unless asked. Keep the GHCR package private.
- Do not `rm -rf` absolute paths (hook blocks it). Confirm before deleting laptop data.
- Commit only when asked. Fix the workflow, not the tests. Light themes only.

---

## 🔧 Commands to Resume
```bash
aws sso login --profile programmable-bio
aws batch describe-jobs --profile programmable-bio --region ap-south-1 \
  --jobs 975b06aa-d537-4b44-af56-1e352689f83d 5494417c-d28d-4bd3-94a2-6fe185565bbb b98dcacd-e1cd-40d0-a965-ef343106701b \
  --query 'jobs[].[jobName,status,statusReason]' --output text
aws s3 ls s3://panbiome-gut-ont-905663668881-ap-south-1/db/k2_gtdb_r226_64GB/
```
Transcript resume (same machine and directory): `claude --resume e4fe2a06-3447-4b6b-a744-2025724ed5df`
