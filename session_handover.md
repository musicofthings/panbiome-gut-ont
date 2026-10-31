# Session Handover
_Generated: 2026-10-31T08:53:05Z_
_Branch: main_
_Trigger: auto | Context at compact: unknown%_
_Compact count this project: 2_

---

## 🎯 Active Task
**What we're building/fixing:**
Run panbiome-gut-ont on AWS Batch (ap-south-1), databases in S3

**Phase:** Roadmap Phase A: first real-data run (zymo-aws1 queued behind Kraken2 build)
**Next action:** aws sso login --profile programmable-bio, then check jobs build-kraken2b / fetch-zymo / zymo-aws1 and review results/zymo-aws1

---

## ✅ Completed This Session
- [ ] (track completed items here)

---

## 🔄 In Progress (Exact Resume Point)
**Branch:** `main`
**Last commit:** `80e804c Resume the Zymo read stream when ENA drops the connection.`
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
claude --resume b1dc8886-bfda-479f-8e87-4ba6cb4b398e
```
- Session ID    : `b1dc8886-bfda-479f-8e87-4ba6cb4b398e`
- Transcript    : `/Users/theranosis_dx/.claude/projects/-Users-theranosis-dx-projects-panbiome-gut-ont/b1dc8886-bfda-479f-8e87-4ba6cb4b398e.jsonl`
- Bound to cwd  : `/Users/theranosis_dx/projects/panbiome-gut-ont`
- Stored at     : `~/.claude/projects/-Users-theranosis-dx-projects-panbiome-gut-ont/b1dc8886-bfda-479f-8e87-4ba6cb4b398e.jsonl`

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
| `.claude/launch.json` | modified |
| `CHANGELOG.md` | modified |
| `README.md` | modified |
| `api/panbiome_api/aws.py` | modified |
| `api/panbiome_api/main.py` | modified |
| `api/panbiome_api/pipeline.py` | modified |
| `api/panbiome_api/settings.py` | modified |
| `api/panbiome_api/tasks.py` | modified |
| `docs/AWS.md` | modified |
| `docs/DATABASES.md` | modified |
| `docs/MONITOR.md` | modified |
| `docs/ROADMAP.md` | modified |
| `infra/aws/batch.yaml` | modified |
| `infra/aws/bin/fetch_url` | modified |
| `infra/aws/bin/head_fastq` | modified |
| _(+16 more files not shown)_ | — |

---

## 🌿 Git Context
```
Branch  : main
Commit  : 80e804c Resume the Zymo read stream when ENA drops the connection.
Status  : M CHANGELOG.md
 M README.md
 M docs/AWS.md
 M docs/ROADMAP.md
?? api/
?? api_docs.md
?? docs/MONITOR.md
?? web/
```

Recent commits:
```
80e804c Resume the Zymo read stream when ENA drops the connection.
7484464 chore(context): save session state — Run panbiome-gut-ont on AWS Batch (ap-south-1), databases in S3 [2026-10-30T18:10:47Z]
1a86a33 chore(context): sync from oncophenomics — panbiome-gut-ont AWS Phase A, zymo-aws1 queued [2026-10-30T16:21:15Z]
e90e98d Queue the first real-data AWS run behind the Kraken2 build.
cc451c9 Run the workflow on AWS Batch with on-demand machines only.
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
