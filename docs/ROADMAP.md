# Roadmap

Phases close on exit criteria, never on a calendar. The only date is the final deadline: paper
submission ~March 2027. Order and goal files follow `GOALS.md`; the exit criteria below include
everything each `/goal` condition checks (plus the Gate 0 additions to Phase 1), and each phase ends at a human gate owned by the maintainer.
Phase 0 (documents, goal `g0-docs`) precedes these and ends at the review of PRD, TECH_SPEC,
ADR-0001 and ADR-0008.

## Phase 1 — Foundation + pipeline on development data (goal `g1-pipeline`)

**Scope:** monorepo scaffolding (`pipeline/`, `web/` skeleton, `scripts/`, `fixtures/`, `.github/`),
`make` targets, pre-commit guards, `make data`, adapters `ovarian-10x`, `synthetic-tma`, `scale`,
`fixture`, canonical validation, asset builders including the pre-aligned H&E pyramid (moved here
from Phase 3 by Gate 0 so the alignment test runs on it), dev UMAP selection, alignment tests. IDs: FR-R2, NFR-13,
NFR-14, NFR-15 (pipeline part), NFR-8 (guards).

**Exit criteria**
1. `make setup` succeeds; `make data TIER=meta,core,he` is idempotent (md5 for supplemental, size vs
   `members.txt` for `outs/`), downloads nothing and prints the file table.
2. Pipeline log lists every raw file opened; none is `transcripts.*`, `morphology*` or `*.zarr.zip`.
3. `make pipeline DATASET=ovarian-10x` validates and prints 407,124 cells, median 178 transcripts/cell,
   gene and cluster counts, sizes per asset family and total.
4. `synthetic-tma` and `scale` build; `scale` ≥ 443,000 cells, ≥ 100 cores, 62 patients, 3 sections,
   23 clusters.
5. T-PIPE-ALIGN-01 (raw image) and T-PIPE-ALIGN-02 (pre-aligned Lanczos pyramid) pass, each printing
   effect size and p-value; the manifest holds each section's source affine and source pixel size.
6. Two runs give identical asset hashes; `make test` passes with pipeline coverage ≥ 85%.
7. No data files or files > 5 MB tracked outside `fixtures/`; repo < 1 GB excluding caches.
8. T-PIPE-QUANT-01 prints the max round-trip error: ≤ 0.5 µm spatial (per section), ≤ 0.1% of the UMAP
   range.
9. Dev UMAP (T-PIPE-UMAP-01): kNN cluster-coherence scores (15 neighbours sharing the 10x cell group)
   printed for the provided Xenium UMAP and the seeded scanpy recompute; the higher one is used; the
   recompute is cached under `$DATA_ROOT/derived/` with its parameters and hash, and a second run reuses
   it without recomputing.

**Gate:** maintainer re-derives µm → H&E pixels by hand for 3 cells and reads `docs/learn/`.
Skill milestone M0.

## Phase 2 — UMAP Atlas (goal `g2-umap`)

**Scope:** web app shell, data layer (worker, decoders, LRU), state store + URL codec v1, UMAP Atlas
view. IDs: FR-U1, FR-U2, FR-U3, FR-U4, FR-G3, FR-G4, FR-G5 (plus FR-G1 shell, FR-P3, FR-P5 basics).

**Exit criteria**
1. `make e2e` passes every test mapped to those IDs on chromium, firefox and webkit.
2. `make bench DATASET=scale`: initial transfer < 5 MB, gene switch p95 < 300 ms over 50 genes,
   median ≥ 55 fps during scripted pan/zoom.
3. axe-core 0 serious/critical; zero console errors; `make verify` exits 0.

**Gate:** private check of the UMAP view by the maintainer. Skill milestone M2.

## Phase 3 — TMA Map + Core Detail (goal `g3-tma-core`)

**Scope:** H&E tile rendering from the Phase 1 pyramid, TMA Map, Core Detail, comparison grid, patient grouping,
overlay opacity. IDs: FR-T1, FR-T2, FR-T3, FR-C1, FR-C2, FR-C3, FR-C4, FR-C5.

**Exit criteria**
1. `make e2e` passes every test mapped to those IDs on three engines (`synthetic-tma`, `scale`).
2. `make bench DATASET=scale` meets every TMA Map and Core Detail budget in TECH_SPEC §7 (budget vs
   measured printed) and still meets NFR-3, NFR-4, NFR-5.
3. Visual test: cell centroids overlay H&E nuclei at single-cell zoom (T-VIS-ALIGN-01).
4. axe-core 0 serious/critical; zero console errors; `make verify` exits 0.
5. `PROGRESS.md` ends with a 5-minute demo script for the lab on dev data.

**Gate:** demo to the lab; schedule the in-person meeting; bring the drive, the handoff list
(BRIEF §4.1) and the meeting agenda in `docs/OPEN_QUESTIONS.md` (questions are held until then). Skill milestone M3.

## Phase 4 — Lab data (goal `g4-lab-data`)

Runs **as soon as the data arrives**; if it has not, Phase 5 proceeds and this phase comes back. It must
finish before paper submission (~March 2027).

**Scope:** `lab` adapter reading Xenium `outs/`, annotation table and TMA map from `$LAB_DATA_DIR`;
per-section H&E alignment (provided transform or documented registration); private overlay (ADR-0008);
figures on lab data. IDs: all M/S re-verified on lab data; NFR-8.

**Exit criteria**
1. `make pipeline DATASET=lab` validates the contract and prints only aggregates: cells, genes,
   clusters (expect 23), sections, cores, patients.
2. Alignment test passes on every section.
3. Phase 2–3 e2e suites (and later suites already complete) pass on the local lab build; every NFR budget
   passes, printed as budget vs measured.
4. `make figures DATASET=lab` writes PNG/SVG under `$LAB_DATA_DIR/figures`.
5. `git status` / `git ls-files` show no lab-derived files; no public build config references `lab`.
6. `make verify` exits 0 on `fixture`; `docs/OPEN_QUESTIONS.md` records the meeting answers.
7. The lab's `analysis_sw_version` (from each section's `experiment.xenium`) is added to
   `atlas_pipeline.xenium.SUPPORTED_ANALYSIS_VERSIONS` only after the spatialdata-io oracle
   (T-PIPE-ORACLE-01) passes on the lab data (ADR-0009 a–b, Gate 1 `[Diego]`).

**Gate:** review figures with Estef. Skill milestones M1 → M4 on real data.

## Phase 5 — Linked views + polish (goal `g5-linked-polish`)

**Scope:** linked selection across views, full URL state and v1 fixtures, exports, figure pack, content
pages, hints, shortcuts, copy link/citation, themes. IDs: FR-G1, FR-G2, FR-G6, FR-G7, FR-P1–FR-P8
(FR-P7 only if its ADR approves), US-1–US-5, NFR-10, NFR-11, NFR-16.

**Exit criteria**
1. `make e2e` passes full journeys US-1 to US-5 on three engines.
2. URL round-trip over 20 random states; committed v1 URL fixtures resolve (NFR-16).
3. PNG/SVG export snapshot tests pass; `make figures DATASET=ovarian-10x` gives identical hashes twice.
4. Lighthouse desktop main view: Performance ≥ 85, Accessibility ≥ 95, Best Practices ≥ 95.
5. Every NFR budget re-measured on `scale` (and on `lab` locally if configured), printed as a table.
6. axe-core 0 serious/critical on every view; zero console errors; `make verify` exits 0.

**Gate:** the maintainer walks through US-1 to US-5. Skill milestone M4.

## Phase 6 — Release readiness with development data (goal `g6-release`)

**Scope:** `make build`, nginx config and `docs/DEPLOY.md` for Jair, README, CITATION.cff,
CONTRIBUTING, LICENSE (MIT pending Q9), fresh-clone reproducibility. IDs: FR-R1, NFR-1, NFR-2, NFR-9,
NFR-14.

**Exit criteria**
1. `make build DATASET=ovarian-10x` produces a static site with a hashed asset manifest.
2. Local nginx with the DEPLOY.md config: full e2e suite passes; curl shows 206 on range requests,
   compression and cache headers.
3. README, CITATION.cff, CONTRIBUTING.md, docs/DEPLOY.md and LICENSE exist.
4. A fresh clone in a temporary directory reproduces identical asset hashes with documented commands.
5. `uv run python scripts/check_docs.py` and `make verify` exit 0; `PROGRESS.md` holds a release
   checklist for the maintainer.

**Gate:** the maintainer pushes, deploys the demo (dev data) and hands `docs/DEPLOY.md` to Jair with
the deployment-step questions (Q8, Q13) from `docs/OPEN_QUESTIONS.md`.
Skill milestone M5.

## After v1

Lab approval (human gate), Zenodo DOI (NFR-9), and the paper link (FR-R1). Could items (FR-U5, FR-T4,
FR-C6, FR-P7) enter only through an ADR.
