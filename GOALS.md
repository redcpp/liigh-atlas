# GOALS.md — phase conditions for `/goal`

One `/goal` per phase. Each condition is ≤ 4,000 characters and asks Claude to print
its evidence, because the evaluator only reads the transcript (it runs no commands).

**Environment (once per shell):**
```bash
export DATA_ROOT=/Volumes/LaCie/atlas-data        # dev data, external drive
export LAB_DATA_DIR=/Volumes/AtlasLab/lab-data    # lab data, encrypted volume (Phase 4 only)
```

**Run** (auto mode, from the repo root; `caffeinate -i` keeps the Mac and the external drive awake):
- Interactive: `caffeinate -i claude --add-dir "$DATA_ROOT"` → auto mode → paste `/goal <text of goals/gN-*.txt>`
- Headless: `caffeinate -i claude --add-dir "$DATA_ROOT" -p "/goal $(cat goals/g0-docs.txt)" --output-format stream-json --verbose`
- Phase 4 adds `--add-dir "$LAB_DATA_DIR"`.

**Order and human gates:**

| Phase | Goal file | Maintainer gate after it | Skill milestone |
|---|---|---|---|
| 0 | `g0-docs` | Review PRD, TECH_SPEC, ADR-0001 (build vs adopt), ADR-0008 (public vs private). Approve or edit. | — |
| 1 | `g1-pipeline` | Re-derive by hand µm → H&E pixels for 3 cells; read `docs/learn/`. | M0 |
| 2 | `g2-umap` | Private check of the UMAP view. | M2 |
| 3 | `g3-tma-core` | **Demo to the lab** with the demo script in PROGRESS.md; schedule the in-person meeting; bring the drive and the handoff list (BRIEF §4.1). | M3 |
| 4 | `g4-lab-data` | Runs **as soon as the data arrives** (if it hasn't, continue with 5 and come back). Must finish before submission. Review figures with Estef. | M1 → M4 on real data |
| 5 | `g5-linked-polish` | Full walkthrough of US-1..US-5 yourself. | M4 |
| 6 | `g6-release` | Push, deploy the demo (dev data), hand `docs/DEPLOY.md` to Jair. | M5 |

## g0-docs

```text
/goal Phase 0 of docs/BRIEF.md is complete: docs/PRD.md, docs/TECH_SPEC.md, docs/DATA_CONTRACT.md, docs/TEST_PLAN.md, docs/ROADMAP.md, docs/OPEN_QUESTIONS.md, docs/learn/00-domain.md, PROGRESS.md and ADRs 0001-0008 in docs/adr/ exist and follow BRIEF section 10. Proof, shown in full in the transcript: (1) `uv run python scripts/check_docs.py` exits 0 and reports that every US/FR/NFR ID in BRIEF appears in PRD with priority and source tag, every Must/Should has at least one Given/When/Then criterion, every ID maps to at least one test in TEST_PLAN, there are no calendar dates except the final deadline, and every open question Q1-Q12 has recipient, what it blocks, status and default assumption; (2) `ls docs docs/adr docs/learn`; (3) `git diff --stat docs/BRIEF.md` is empty. Constraints: no application code yet except scripts/check_docs.py; no data downloaded; ADR 0001 (build vs adopt) compares options against FR-T1, FR-C3, FR-G6 and NFR-16 with a clear decision; ROADMAP follows the phase order in GOALS.md. Or stop after 30 turns and list exactly what is missing.
```

## g1-pipeline

```text
/goal Phase 1 (foundation + pipeline on development data) from docs/ROADMAP.md is complete. $DATA_ROOT points to the external drive. Proof, each output shown in full in the transcript: (1) `make setup` succeeds; (2) `make data TIER=list` prints the members of the remote full-bundle ZIP with sizes without downloading it, and shows the server's Accept-Ranges header; (3) `make data TIER=meta,core,he` stores under $DATA_ROOT/raw only the files in BRIEF section 4.2 for those tiers, verifies md5 for supplemental files and CRC-32 for extracted members, and `du -sh $DATA_ROOT/raw` is under 7 GB; (4) `make pipeline DATASET=ovarian-10x` exits 0, validates the canonical data contract and prints cell count = 407124, median transcripts per cell = 178, gene count, cluster count, and asset sizes per family plus total; (5) `make pipeline DATASET=synthetic-tma` and `make pipeline DATASET=scale` exit 0 and print sections, cores, patients and cells (scale: at least 443000 cells, at least 100 cores, 62 patients, 3 sections, 23 clusters); (6) an automated alignment test passes: hematoxylin intensity (color deconvolution) at 1,000 random cell centroids mapped into H&E pixels is significantly higher than at 1,000 random in-tissue points, reporting effect size and p-value; (7) running the ovarian-10x pipeline twice produces identical asset hashes; (8) `make test` exits 0 with pipeline line coverage at least 85%; (9) `git ls-files` shows no data extensions or files over 5 MB outside fixtures/ and `du -sh .` of the repo is under 1 GB excluding node_modules and .venv. Constraints: nothing written to disk outside the repo, $DATA_ROOT and tool caches; web app limited to scaffolding; PROGRESS.md and docs/learn/ updated. Or stop after 40 turns and list what is missing.
```

## g2-umap

```text
/goal Phase 2 (UMAP Atlas view) is complete: FR-U1, FR-U2, FR-U3, FR-U4, FR-G3, FR-G4 and FR-G5 meet their acceptance criteria in docs/PRD.md on the scale dataset. Proof, shown in full in the transcript: (1) `make e2e` passes every test mapped to those IDs in docs/TEST_PLAN.md on chromium, firefox and webkit; (2) `make bench DATASET=scale` reports initial transfer under 5 MB, gene-switch p95 under 300 ms over 50 random genes, and median fps of at least 55 during the scripted pan/zoom; (3) axe-core reports 0 serious or critical violations on the view; (4) zero console errors across the e2e run; (5) `make verify` exits 0. Constraints: no lab data; all Phase 1 tests still pass; no threshold lowered; docs/perf.md, PROGRESS.md and docs/learn/ updated. Or stop after 40 turns and report what is missing together with the measured numbers.
```

## g3-tma-core

```text
/goal Phase 3 (TMA Map + Core Detail) is complete: FR-T1, FR-T2, FR-T3, FR-C1, FR-C2, FR-C3, FR-C4 and FR-C5 meet their acceptance criteria in docs/PRD.md on the synthetic-tma and scale datasets. Proof, shown in full in the transcript: (1) `make e2e` passes every test mapped to those IDs in docs/TEST_PLAN.md on chromium, firefox and webkit; (2) `make bench DATASET=scale` meets every Core Detail and TMA Map budget defined in the performance plan of docs/TECH_SPEC.md (print budget vs measured for each) and still meets NFR-3, NFR-4 and NFR-5; (3) a visual test confirms cell centroids overlay the H&E nuclei in Core Detail at single-cell zoom; (4) axe-core 0 serious or critical violations; zero console errors; (5) `make verify` exits 0. Constraints: no lab data; Phase 1-2 tests still pass; no threshold lowered; docs/perf.md, PROGRESS.md and docs/learn/ updated; PROGRESS.md ends with a 5-minute demo script for the lab using the dev data. Or stop after 40 turns and report what is missing with measured numbers.
```

## g4-lab-data

```text
/goal Phase 4 (lab data) is complete. Precondition: the lab files from BRIEF section 4.1 are in $LAB_DATA_DIR on an encrypted volume outside the repo, and docs/OPEN_QUESTIONS.md records the answers received at the meeting. Proof, shown in full in the transcript: (1) a lab adapter reads the Xenium outs/ files, the annotation table and the TMA map from $LAB_DATA_DIR into the canonical data contract; (2) `make pipeline DATASET=lab` exits 0, validates the contract and prints only aggregate counts: cells, genes, clusters (expect 23), sections, cores and patients; (3) H&E alignment per section is resolved (provided transform or documented registration) and the alignment test from Phase 1 passes on every section; (4) the Phase 2-3 e2e suites (and any later suites already complete) pass against the lab build served locally, and every NFR budget passes, printed as budget vs measured; (5) `make figures DATASET=lab` renders the views in docs/figures.yaml to PNG/SVG under $LAB_DATA_DIR/figures; (6) `git status` and `git ls-files` show no lab-derived files and no public build config references the lab dataset; (7) `make verify` exits 0 on the fixture. Constraints: never print cell-level values, patient identifiers or clinical fields; no deployment of lab data anywhere; PROGRESS.md and docs/OPEN_QUESTIONS.md updated. Or stop after 30 turns and report what is missing.
```

## g5-linked-polish

```text
/goal Phase 5 (linked views + polish) is complete: FR-G1, FR-G2, FR-G6, FR-G7 and FR-P1 through FR-P8 (FR-P7 only if its ADR says so) meet their acceptance criteria in docs/PRD.md. Proof, shown in full in the transcript: (1) `make e2e` passes full journeys for US-1 through US-5 on chromium, firefox and webkit; (2) a URL round-trip test serializes 20 random view states, reloads each and gets identical state, and committed v1 URL fixtures still resolve (NFR-16); (3) PNG/SVG export snapshot tests pass and `make figures DATASET=ovarian-10x` reproduces identical figure hashes on two runs; (4) Lighthouse desktop on the main view: performance at least 85, accessibility at least 95, best practices at least 95; (5) every NFR budget in docs/perf.md re-measured on the scale dataset, and on the lab dataset locally if $LAB_DATA_DIR is configured, printed as a budget vs measured table; (6) axe-core 0 serious or critical violations on every view; zero console errors; (7) `make verify` exits 0. Constraints: no lab data in git or public builds; earlier phase tests still pass; no threshold lowered; PROGRESS.md and docs/learn/ updated. Or stop after 50 turns and report what is missing.
```

## g6-release

```text
/goal Phase 6 (release readiness with development data) is complete. Proof, shown in full in the transcript: (1) `make build DATASET=ovarian-10x` produces a static site directory with a hashed asset manifest; (2) serving that directory with a local nginx (not a Docker VM) using the config in docs/DEPLOY.md, the full e2e suite passes against it, and curl output shows HTTP range requests (206), compression and cache headers working; (3) README (what, quickstart, pipeline, deploy, cite), CITATION.cff, CONTRIBUTING.md, docs/DEPLOY.md written for the LIIGH infrastructure admin (nginx, Let's Encrypt, subdomain, quota at least 10 GB), and a LICENSE (MIT, pending confirmation in Q9) all exist; (4) a fresh clone in a temporary directory runs setup + data + pipeline + build with documented commands and reproduces identical asset hashes; (5) `uv run python scripts/check_docs.py` and `make verify` exit 0. Constraints: no push, no deploy, no lab data; PROGRESS.md updated with a release checklist for the maintainer. Or stop after 30 turns and report what is missing.
```

