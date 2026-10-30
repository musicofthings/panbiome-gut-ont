# Session Handover
_Generated: 2026-10-30T10:58:58Z_
_Branch: main_
_Trigger: auto | Context at compact: unknown%_
_Compact count this project: 1_

---

## 🎯 Active Task
**What we're building/fixing:**
creating anything that costs money

**Phase:** Phase 4 test data in `/tmp/panbiome-phase4` | A
**Next action:** Please run: ```bash aws sso login --profile programmable-bio ``` Once you're signed in, I'll check the region, machine

---

## ✅ Completed This Session
- [ ] (track completed items here)

---

## 🔄 In Progress (Exact Resume Point)
**Branch:** `main`
**Last commit:** `e2e1e5c chore(context): sync from oncophenomics.local — panbiome-gut-ont v0.1.1 publish [2026-10-27T21:16:33Z]`
**Next immediate action:** Please run: ```bash aws sso login --profile programmable-bio ``` Once you're signed in, I'll check the region, machine

---

## 📋 Remaining Work
1. User decision: make `panbiome-gut-ont-core` public, or keep it private and authenticate pulls. Public cannot be switched back.
2. EPI2ME: Workflows, Import workflow, Import from GitHub, `musicofthings/panbiome-gut-ont`. Confirm the form renders from `nextflow_schema.json`. Not run here because the app is not installed.
3. Full databases were not downloaded. Kraken2 GTDB v226 archive is 537801719465 bytes. sylph match is `gtdb-r226-c200-dbv2.syl2db` (14272284891 bytes) plus r226 bac120/ar53 maps. After any Langmead extract, run `bracken-build -d DB -t THREADS -k 35 -l 1000`.
4. Still not run on real databases: SemiBin2, CheckM2, GTDB-Tk, AMRFinderPlus, geNomad, eggNOG, Emu. SemiBin2 downloads GTDB when `--reference-db` is unset.
5. eggNOG image host `eggnogdb.embl.de` does not resolve. eggNOG 5.0.2 files are on `https://eggnog5.embl.de/download/emapperdb-5.0.2/`. Do not use the eggNOG-mapper v3 / eggNOG 7 download for image 2.1.15.

---

## 🏗 Architecture Decisions Made
| Decision | Rationale | Date |
|----------|-----------|------|
| Shotgun taxonomy pair is GTDB r226 for Kraken2 and sylph | Langmead prebuilt Kraken archive is v226. Reconcile matches names only when both databases share a taxonomy. | 2026-10-28 |
| GTDB-Tk stays optional and uses R232 | Pinned GTDB-Tk 2.8.0 accepts R232. R226 stops at GTDB-Tk 2.6.1. Package is about 61 GB compressed and about 140 GB RAM. | 2026-10-28 |
| `medaka_model` stays `r1041_e82_400bps_sup_v5.0.0` | Name is listed by the image. Weights are downloaded into the work directory and passed as a file. Image default consensus model is v5.2.0. | 2026-10-28 |
| `bracken_read_len` stays 1000 | Tiny database was built with `bracken-build -l 1000`. Langmead archive ships Bracken lengths through 300-mers. | 2026-10-28 |
| `big_memory` stays 32 GB | Phase 4 used a CLI override of 8 GB. Medaka peak RSS was 7 GB. The production default was left for a 3–4 Gb sample. | 2026-10-28 |
| Publish over HTTPS, not SSH | `git@github.com` returned `Permission denied (publickey)`. `gh` is logged in as `musicofthings`. | 2026-10-28 |
| Core image tag remains 0.1.0 | Workflow fixes are in the Nextflow scripts. `bin/` is taken from the project directory. The image was not rebuilt. | 2026-10-28 |

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
| `.gitignore` | modified |
| `docs/AWS.md` | modified |
| `docs/DATABASES.md` | modified |
| `infra/aws/batch.yaml` | modified |
| `infra/aws/bin/fetch_url` | modified |
| `infra/aws/build_kraken2.nf` | modified |
| `infra/aws/fetch_dbs.nf` | modified |
| `infra/aws/run.sh` | modified |
| `modules/assembly.nf` | modified |
| `nextflow.config` | modified |

---

## 🌿 Git Context
```
Branch  : main
Commit  : e2e1e5c chore(context): sync from oncophenomics.local — panbiome-gut-ont v0.1.1 publish [2026-10-27T21:16:33Z]
Status  : M .gitignore
 M docs/DATABASES.md
 M modules/assembly.nf
 M nextflow.config
?? api_docs.md
?? docs/AWS.md
?? infra/
```

Recent commits:
```
e2e1e5c chore(context): sync from oncophenomics.local — panbiome-gut-ont v0.1.1 publish [2026-10-27T21:16:33Z]
060221c Record the GHCR push of the core image.
f0590ff Record the Phase 7 publish checks.
536588d Defer sample publishDir paths until meta exists.
4396d8e Move workflow.onComplete into the entry workflow.
```

---

## ⚠️ Critical Rules
- Never commit secrets, `.env`, or API keys.
- Do not retune placeholder thresholds, `medaka_model`, `bracken_read_len`, `sylph_args`, `min_ani`, or `big_memory` unless asked.
- Do not download anything over 1 GB without asking. Kraken2 GTDB v226 and GTDB-Tk R232 do not fit on this disk.
- Never index a human genome into the repo. T2T-CHM13 stays outside the repo.
- Do not `rm -rf` an absolute path. A safety hook blocks it.
- Do not `docker push` or create a git tag unless asked. The image tag `0.1.0` is already pushed.
- Making the GHCR package public cannot be undone.
- Fix the workflow, not the tests, unless a test is wrong.
- Phase 4 inputs and outputs live under `/tmp/panbiome-phase4/`, outside the repo.

---

## 🧬 Bioinformatics Context (if applicable)
- Assay: ONT gut shotgun. Pinned core image `ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0`, local id `e1dd5c49b4bc`, about 2.04 GB.
- Small-data run: ERR2906227 prefix, 52677 reads, 208636938 bases. Eight species kept where Kraken2/Bracken and sylph agreed. QC status FAIL and control status MISSING are expected on that prefix.
- Flye: 467 contigs, 7928514 bp, N50 20795. Medaka: 467 contigs, 7858240 bp, N50 20573, model file `r1041_e82_400bps_sup_v5.0.0_model_pt.tar.gz`.
- Host decoy was phage lambda, so host fraction was about 0. That does not validate human depletion.
- Reconcile rule `both` applies the two-method test only when both shotgun methods are present.
- Docker VM on this laptop has about 31 GB RAM and 16 CPUs. GTDB-Tk bacterial classification asks for about 140 GB.
- Record of commands: `docs/VALIDATION_LOG.md`.

---
_Auto-updated by `pre-compact.sh` hook and `/handover` skill._
_Read this at the start of every session. Update with `/handover`._
