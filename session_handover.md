# Session Handover
_Generated: 2026-10-27T21:15:36Z_
_Branch: main_
_Trigger: user request | Context at compact: n/a_
_Compact count this project: 1_

---

## 🎯 Active Task
**What we're building/fixing:**
panbiome-gut-ont v0.1.1 is published. The Nextflow workflow is on GitHub and the core image is on GHCR. The package is still private, and the EPI2ME desktop import has not been opened on this machine.

**Phase:** Phase 7 publish is done except package visibility and the EPI2ME check.
**Next action:** Ask before making `ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0` public. That change cannot be undone. Then, on a machine with EPI2ME, import `musicofthings/panbiome-gut-ont` and confirm the settings form renders from `nextflow_schema.json`.

---

## ✅ Completed This Session
- [x] Phases 0–3: environment, local core image, stub DAG, tool-flag fixes (Kraken2 `--output -` removed, GTDB-Tk `--skip_ani_screen` removed, sample-sheet and report stubs)
- [x] Phase 4: real tools on the first 209715200 bytes of ENA ERR2906227 with a ten-RefSeq-genome Kraken2/Bracken/sylph database and phage lambda NC_001416.1 as the host decoy. Run 1 profiling exit 0. Medaka weights download fixed. Run 3 Flye and Medaka exit 0. AMRFinderPlus exited 1 with no database. Binning not run.
- [x] Phase 5: database sizes and commands only. No download. Shotgun pair is GTDB r226. GTDB-Tk for image 2.8.0 is R232 and optional. About 83 GiB free, so the Kraken archive and GTDB-Tk package do not fit.
- [x] Phase 6: pytest 8 passed. `nextflow inspect` resolved pinned containers. README verification table and `CHANGELOG.md` updated. `manifest.version` is `0.1.1`. Parameter defaults unchanged. Core image tag stays `0.1.0`.
- [x] Phase 7: public repo https://github.com/musicofthings/panbiome-gut-ont branch `main`. Nextflow 26.10.4 CI stub fixed (`workflow.onComplete` assignment, `publishDir` closures). Actions run 40578822436 passed test and stub. Image pushed. Digest `sha256:5ae5f2c17be6ad2cf9ebe4b9492bea189dc994ccb4b07ac6a084c003c0c7c114`. Package is private and not linked to the repo.

---

## 🔄 In Progress (Exact Resume Point)
**Branch:** `main`
**Last commit:** `060221c Record the GHCR push of the core image.`
**Next immediate action:** Leave the GHCR package private until the user says to make it public. Do not start another device-code flow unless they are at the browser.

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
```bash
# On any machine after git pull:
git pull origin main
# This repo has no scripts/session_sync.sh. The kit script lives in the context-engineering-kit plugin.
# Read session_handover.md, then continue only when asked.

# Repo and image:
# https://github.com/musicofthings/panbiome-gut-ont
# ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0
# Package page: https://github.com/users/musicofthings/packages/container/package/panbiome-gut-ont-core
```

---

## 📁 Files Modified This Session
| File | Status |
|------|--------|
| `modules/assembly.nf` | Medaka weight download; GTDB-Tk flag removed; `publishDir` closures |
| `modules/profiling.nf` | Kraken2 `--output -` removed; `publishDir` closures |
| `modules/qc.nf` | `publishDir` closures |
| `modules/ingest.nf` | Stub copies the supplied sample sheet |
| `modules/reporting.nf` | Stub writes one HTML report per alias |
| `main.nf` | `workflow.onComplete` assigned inside the entry workflow |
| `nextflow.config` | `manifest.version` `0.1.1` only. Params unchanged. |
| `README.md` | Verification table and r226 example paths |
| `CHANGELOG.md` | v0.1.1 fixes |
| `docs/DATABASES.md` | r226 pair, sizes, eggNOG host, GTDB-Tk R232 |
| `docs/VALIDATION_LOG.md` | Phases 0–7 |
| `.gitignore` | Also excludes `stub_output*/`, `.DS_Store`, `.claude/` |

---

## 🌿 Git Context
```
Branch  : main
Commit  : 060221c
Status  : clean before this handover file
Remote  : https://github.com/musicofthings/panbiome-gut-ont.git
```

Recent commits:
```
060221c Record the GHCR push of the core image.
f0590ff Record the Phase 7 publish checks.
536588d Defer sample publishDir paths until meta exists.
4396d8e Move workflow.onComplete into the entry workflow.
00a4dfc panbiome-gut-ont v0.1.1
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
