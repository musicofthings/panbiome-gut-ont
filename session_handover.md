# Session Handover
_Generated: 2026-10-30T18:10:48Z_
_Branch: main_
_Trigger: session-end | Context at compact: unknown%_
_Compact count this project: 1_

---

## 🎯 Active Task
**What we're building/fixing:**
Run panbiome-gut-ont on AWS Batch (ap-south-1), databases in S3

**Phase:** Roadmap Phase A: first real-data run (zymo-aws1 queued behind Kraken2 build)
**Next action:** aws sso login --profile programmable-bio, then check jobs build-kraken2b / fetch-zymo / zymo-aws1 and review results/zymo-aws1

---

## ✅ Completed This Session
- CloudFormation stack `panbiome-gut-ont-batch` deployed (user runs deploys; the auto-mode classifier blocks Claude from applying IaC). On-demand only since 2026-10-30 14:20 UTC: spot CE removed, `panbiome-default` and `panbiome-ondemand` share `OnDemandComputeEnv` (MinvCpus 0), `panbiome-build` on `BuildComputeEnv` (1000 GB disk). Head job definition rev 2 has a 72 h timeout (`HeadTimeoutSeconds`).
- Core image mirrored to ECR (`panbiome-gut-ont-core:0.1.0`, same digest as GHCR).
- AWS stub run `stub-test4` passed 48/48.
- Databases in `s3://panbiome-gut-ont-905663668881-ap-south-1/db/` (~79 GB): sylph r226 + map, CheckM2, geNomad, AMRFinderPlus (`amrfinder/latest`), eggNOG 5.0.2, T2T-CHM13 minimap2 index.
- README "Run it on AWS", `docs/AWS.md` (incl. "Chaining runs"), `docs/ROADMAP.md` (Phase A real run, Phase B web frontend, Phase C EPI2ME), CHANGELOG Unreleased.
- Commits pushed to main: cc451c9, e90e98d.

---

## 🔄 In Progress (Exact Resume Point)
**Branch:** `main`
**Last commit:** `1a86a33 chore(context): sync from oncophenomics — panbiome-gut-ont AWS Phase A, zymo-aws1 queued [2026-10-30T16:21:15Z]`
**Next immediate action:** aws sso login --profile programmable-bio, then check jobs build-kraken2b / fetch-zymo / zymo-aws1 and review results/zymo-aws1

---

## 📋 Remaining Work
1. Phase A: verify Kraken2 DB, review `zymo-aws1`, tune memory/time from trace, record cost (tag `project=panbiome-gut-ont`).
2. Optional: EventBridge → SNS email on head-job completion (needs an email address; user deploys).
3. Phase B web frontend — open decisions in `docs/ROADMAP.md` (who signs in, data residency, CloudFront vs Cloudflare Pages, custom vs Seqera Platform).
4. Phase C EPI2ME — import from GitHub not yet tried; check bundled Nextflow version vs the 26.x needed for `awsbatch`.
5. Laptop cleanup (~30 GB Docker images) — only with explicit approval.
6. X-family quota increase (full 644 GB Kraken2) — user's decision.

---

## 🏗 Architecture Decisions Made
| Decision | Rationale | Date |
|----------|-----------|------|
| (none yet) | — | — |

---

## 🔧 Commands to Resume

**This exact conversation** (SDK/CLI transcript resume):
```bash
# Same machine AND same directory it started in:
claude --resume e4fe2a06-3447-4b6b-a744-2025724ed5df
```
- Session ID    : `e4fe2a06-3447-4b6b-a744-2025724ed5df`
- Transcript    : `/Users/theranosis_dx/.claude/projects/-Users-theranosis-dx-projects-panbiome-gut-ont/e4fe2a06-3447-4b6b-a744-2025724ed5df.jsonl`
- Bound to cwd  : `/Users/theranosis_dx/projects/panbiome-gut-ont`
- Stored at     : `~/.claude/projects/-Users-theranosis-dx-projects-panbiome-gut-ont/e4fe2a06-3447-4b6b-a744-2025724ed5df.jsonl`

> ⚠️ Transcript resume is **cwd-bound**. It only works from the same directory
> on the same machine. If this session started in a git **worktree**, that
> worktree's path is the cwd — resuming from `main` (or after the worktree is
> deleted) will silently start a *fresh* session. Per the Agent SDK docs, the
> robust cross-host / cross-worktree path is **not** transcript resume — it's
> this handover file: read it into a new session's prompt as application state.

**Project state** (any machine — the robust path):
```bash
git pull origin main
bash scripts/session_sync.sh --load

# In Claude Code:
# /context-health     — verify hooks are wired
# /handover           — review this file
# /token-status       — check context usage
```

---

## 📁 Files Modified This Session
| File | Status |
|------|--------|
| `docs/AWS.md` | modified |
| `docs/DATABASES.md` | modified |
| `docs/ROADMAP.md` | modified |
| `infra/aws/batch.yaml` | modified |
| `infra/aws/bin/fetch_url` | modified |
| `infra/aws/bin/head_fastq` | modified |
| `infra/aws/build_kraken2.nf` | modified |
| `infra/aws/fetch_dbs.nf` | modified |
| `infra/aws/fetch_test_reads.nf` | modified |
| `infra/aws/run.sh` | modified |
| `modules/assembly.nf` | modified |
| `nextflow.config` | modified |
| `session_handover.md` | modified |

---

## 🌿 Git Context
```
Branch  : main
Commit  : 1a86a33 chore(context): sync from oncophenomics — panbiome-gut-ont AWS Phase A, zymo-aws1 queued [2026-10-30T16:21:15Z]
Status  : ?? api_docs.md
```

Recent commits:
```
1a86a33 chore(context): sync from oncophenomics — panbiome-gut-ont AWS Phase A, zymo-aws1 queued [2026-10-30T16:21:15Z]
e90e98d Queue the first real-data AWS run behind the Kraken2 build.
cc451c9 Run the workflow on AWS Batch with on-demand machines only.
7c7f97b chore(context): pre-compact snapshot [2026-10-30T10:58:57Z] ctx=unknown%
e2e1e5c chore(context): sync from oncophenomics.local — panbiome-gut-ont v0.1.1 publish [2026-10-27T21:16:33Z]
```

---

## ⚠️ Critical Rules
- Never commit secrets, `.env`, or API keys. Leave `api_docs.md` (tool-generated) uncommitted.
- Do not retune `medaka_model`, `bracken_read_len`, `sylph_args`, `min_ani`, or `big_memory` unless asked.
- No downloads >1 GB to the laptop without asking. No `docker push` or git tags unless asked. Keep the GHCR package private.
- Do not `rm -rf` absolute paths (hook blocks it). Confirm before deleting laptop data.
- Commit only when asked. Fix the workflow, not the tests. Light themes only.

---

## 🧬 Bioinformatics Context (if applicable)
- Not configured for this project

---
_Auto-updated by `pre-compact.sh` hook and `/handover` skill._
_Read this at the start of every session. Update with `/handover`._
