# Test Plan

Version 0.1 (Phase 0). Strategy and measurement rules: `docs/adr/0007-testing-and-performance.md`.
Every test title starts with its test ID and lists the requirement IDs it covers (e.g.
`T-E2E-G4-01 [FR-G4] autocomplete is case-insensitive`), so traceability is checkable by script.
From Phase 1 a script also checks that every test ID below exists in the code. Tests of Could items
(FR-U5, FR-T4, FR-C6, FR-P7) run only if their ADR approves the feature.

Datasets: `fixture` (CI), `synthetic-tma`, `scale` (≥ 443K cells; budgets), `ovarian-10x` (real dev
data), `lab` (Phase 4, local only, no snapshots).

## Test catalog

| Test ID | Type | What it verifies | Dataset | Phase |
|---|---|---|---|---|
| T-PIPE-DATA-01 | integration | `make data` is idempotent: md5 for supplemental files, size vs `members.txt` for `outs/`, downloads nothing present | ovarian-10x | 1 |
| T-PIPE-GUARD-01 | unit | Open-guard raises on `transcripts.*`, `morphology*`, `*.zarr.zip`; log lists every raw file opened | fixture | 1 |
| T-PIPE-CONTRACT-01 | contract | `ovarian-10x` validates: 407,124 cells, median 178 transcripts/cell, 18 clusters, all invariants | ovarian-10x | 1 |
| T-PIPE-CONTRACT-02 | contract | `synthetic-tma` and `scale` validate; `scale` ≥ 443,000 cells, ≥ 100 cores, 62 patients, 3 sections, 23 clusters | synthetic-tma, scale | 1 |
| T-PIPE-CORES-01 | unit | Cores non-overlapping, inside sections, contiguous cell ranges after Morton ordering | fixture | 1 |
| T-PIPE-QUANT-01 | unit | uint16 coordinate quantization error ≤ 0.1% of UMAP range and ≤ 0.5 µm spatial | fixture | 1 |
| T-PIPE-EXPR-01 | unit | Per-gene sparse/dense uint8 encoder round-trips; format picks the smaller; `max_v` stored | fixture | 1 |
| T-PIPE-ALIGN-01 | integration | Hematoxylin at 1,000 centroids mapped to H&E px > 1,000 random in-tissue points; effect size + p-value | ovarian-10x | 1 |
| T-PIPE-HE-01 | unit | H&E warped to µm frame: tile geometry, per-core crops, thumbnails, deterministic WebP | fixture | 3 |
| T-PIPE-REPRO-01 | integration | Two pipeline runs produce byte-identical manifests | ovarian-10x, fixture | 1 |
| T-PIPE-SIZE-01 | integration | Size report per asset family; `scale` total ≤ 5 GB | scale | 1 |
| T-PIPE-PALETTE-01 | unit | 23-color palette min pairwise ΔE2000 ≥ 10 under normal, protan, deutan simulation | none | 2 |
| T-PIPE-PRIV-01 | unit | Private datasets log aggregates only; logging filter rejects cell-level rows | fixture | 1 |
| T-PIPE-COV-01 | static | Pipeline line coverage ≥ 85% | fixture | 1 |
| T-WEB-URL-01 | unit | URL codec round-trips 20 random states; URL ≤ 2,000 characters | none | 2 |
| T-WEB-URL-02 | unit | Committed v1 URL fixtures parse to their recorded states | none | 5 |
| T-WEB-DECODE-01 | unit | Worker decoders for uint16/uint8 columns and per-gene files | fixture | 2 |
| T-WEB-LRU-01 | unit | Gene LRU cache eviction and abort of superseded requests | none | 2 |
| T-WEB-SEL-01 | unit | Selection masks from cluster, core, patient and lasso polygon definitions | fixture | 2 |
| T-WEB-SEARCH-01 | unit | Autocomplete: case-insensitive, exact-prefix first, closest symbols for unknown input | fixture | 2 |
| T-WEB-COV-01 | static | Web `state/` and `data/` line coverage ≥ 80% | none | 2 |
| T-E2E-US1-01 | e2e | Journey: search gene → UMAP and tissues colored, color kept across views | fixture, scale | 5 |
| T-E2E-US2-01 | e2e | Journey: TMA Map → click core → H&E next to annotated cells | fixture | 5 |
| T-E2E-US3-01 | e2e | Journey: open four cores from different patients side by side | fixture | 5 |
| T-E2E-US4-01 | e2e | Journey: copy link → open in a fresh context → same view | fixture | 5 |
| T-E2E-US5-01 | e2e | Journey: first visit hints lead to a gene-colored UMAP; hints dismissible | fixture | 5 |
| T-MAN-US5-01 | manual | Moderated test, ≥ 3 people outside the lab, median ≤ 60 s to explain and color by gene | ovarian-10x | 5 |
| T-E2E-G1-01 | e2e | View switcher reaches the three views with no full reload | fixture | 2 |
| T-E2E-G2-01 | e2e | Selection in one view highlights the same cells in the others | fixture | 5 |
| T-E2E-G2-02 | e2e | Hovering a core highlights its cells on the UMAP | fixture | 5 |
| T-E2E-G3-01 | e2e | Color by cluster, patient, core, gene; legend or color bar matches | fixture | 2 |
| T-E2E-G4-01 | e2e | Autocomplete with case variants, keyboard navigation | fixture | 2 |
| T-E2E-G4-02 | e2e | Unknown gene shows empty state with suggestions | fixture | 2 |
| T-E2E-G5-01 | e2e | Legend toggle, isolate, hover highlight over 23 clusters | scale | 2 |
| T-E2E-G6-01 | e2e | Reloading a URL restores dataset release, view, color, filters, selection, camera | fixture | 5 |
| T-E2E-G7-01 | e2e | PNG ≥ 2,126 px wide and SVG with vector legend/axes/scale bar download | fixture | 5 |
| T-VIS-EXPORT-01 | visual | Exported PNG matches on-screen content (chromium snapshot) | fixture | 5 |
| T-E2E-U1-01 | e2e | Drawn instance count equals dataset cell count | scale | 2 |
| T-E2E-U2-01 | e2e | Hover card shows cluster, patient, core and gene value | fixture | 2 |
| T-E2E-U3-01 | e2e | Hidden/isolated clusters are not drawn or pickable; state in URL | fixture | 2 |
| T-E2E-U4-01 | e2e | Lasso selects enclosed cells, shows count, links to other views | fixture | 2 |
| T-E2E-U5-01 | e2e | 3D UMAP toggle renders and rotates (only if its ADR approves) | fixture | 5 |
| T-E2E-T1-01 | e2e | Sections drawn with cores at canonical centers/radii (≤ 1 µm) and labeled | synthetic-tma | 3 |
| T-E2E-T2-01 | e2e | Click or Enter on a core opens its Core Detail and updates the URL | fixture | 3 |
| T-E2E-T3-01 | e2e | Hover/focus on a core shows H&E thumbnail and patient | fixture | 3 |
| T-E2E-T4-01 | e2e | Provisional Plotly view embedded (only if the lab provides it and its ADR approves) | fixture | 3 |
| T-E2E-C1-01 | e2e | Pan/zoom in one panel moves the other to the same µm viewport | fixture | 3 |
| T-E2E-C2-01 | e2e | Zoom reaches ≤ 0.25 µm per screen pixel with full-resolution tiles | fixture | 3 |
| T-E2E-C3-01 | e2e | Up to 6 cores side by side with shared color/legend, encoded in URL | fixture | 3 |
| T-E2E-C4-01 | e2e | "All cores of this patient" opens exactly that patient's cores | synthetic-tma | 3 |
| T-E2E-C5-01 | e2e | Overlay opacity slider 0–100% changes cell opacity; value in URL | fixture | 3 |
| T-E2E-C6-01 | e2e | Cell outlines appear above a zoom threshold (only if its ADR approves) | fixture | 3 |
| T-VIS-ALIGN-01 | visual | Cell centroids overlay H&E nuclei in Core Detail at single-cell zoom | synthetic-tma | 3 |
| T-E2E-P1-01 | e2e | About, Methods, How to cite, License & provenance pages reachable; 10x CC BY credit present | fixture | 5 |
| T-E2E-P2-01 | e2e | First-visit hints dismiss permanently; `?` opens shortcuts panel | fixture | 5 |
| T-E2E-P3-01 | e2e | Loading progress; failed asset shows error and retries only that asset | fixture | 2 |
| T-E2E-P3-02 | e2e | WebGL-unsupported fallback page | fixture | 2 |
| T-E2E-P3-03 | e2e | Empty state when filters hide every cell, with reset | fixture | 2 |
| T-E2E-P4-01 | e2e | Copy link and Copy citation fill the clipboard and announce it | fixture | 5 |
| T-E2E-P5-01 | e2e | Only configured datasets selectable; synthetic badge in views and exports | fixture | 2 |
| T-E2E-P6-01 | e2e | Dark and light OS schemes applied; axe contrast passes in both | fixture | 5 |
| T-E2E-P7-01 | e2e | QC page links each section's `analysis_summary.html` (only if its ADR approves) | fixture | 5 |
| T-INT-FIG-01 | integration | `make figures` twice → identical PNG/SVG hashes | ovarian-10x | 5 |
| T-INT-STATIC-01 | integration | Full e2e suite passes against a plain static server with no runtime | fixture | 6 |
| T-INT-NGINX-01 | integration | Local nginx with DEPLOY.md config: 206 on range, gzip, immutable cache headers | ovarian-10x | 6 |
| T-INT-FRESH-01 | integration | Fresh clone: setup + data + pipeline + build reproduce identical hashes | ovarian-10x | 6 |
| T-INT-PUBGUARD-01 | integration | Public build fails with a private dataset or overlay; patient IDs pseudonymous | fixture | 4 |
| T-E2E-R1-01 | e2e | Footer and How-to-cite page link to the source repository and show the app version | fixture | 5 |
| T-STATIC-REPO-01 | static | README, LICENSE, CITATION.cff, CONTRIBUTING present; footer links to repository | none | 6 |
| T-STATIC-CITE-01 | static | CITATION.cff valid; DOI present at release | none | 6 |
| T-STATIC-TRACE-01 | static | Every M/S ID has ≥ 1 e2e test and every test ID in this plan exists in code | none | 1 |
| T-MAN-ZENODO-01 | manual | Maintainer archives the release on Zenodo and records the DOI | none | 6 |
| T-E2E-XB-01 | e2e | Whole suite runs on chromium, firefox and webkit | fixture | 2 |
| T-E2E-MOBILE-01 | e2e | Mobile viewport: read-only navigation works, no layout overflow | fixture | 5 |
| T-E2E-CONSOLE-01 | e2e | Global fixture fails any test with a console error or page error | fixture | 2 |
| T-E2E-NFR16-01 | e2e | A URL pinned to a previous release loads it, or the current one with a notice | fixture | 5 |
| T-A11Y-AXE-01 | a11y | axe-core 0 serious/critical on every view | fixture | 2 |
| T-A11Y-KBD-01 | a11y | Keyboard-only walkthrough of every control with visible focus | fixture | 5 |
| T-A11Y-COLOR-01 | a11y | Every color encoding has a text equivalent (legend labels, hover card) | fixture | 2 |
| T-LH-01 | lighthouse | Desktop main view: Performance ≥ 85, Accessibility ≥ 95, Best Practices ≥ 95 | fixture, scale | 5 |
| T-BENCH-LOAD-01 | bench | < 5 MB transferred before interactive; time to interactive < 3 s | scale | 2 |
| T-BENCH-GENE-01 | bench | Gene switch p95 < 300 ms over 50 random genes, cold cache | scale | 2 |
| T-BENCH-FPS-01 | bench | Median ≥ 55 fps during scripted pan/zoom with all cells | scale | 2 |
| T-BENCH-INTER-01 | bench | Hover < 50 ms, cluster toggle < 100 ms, lasso < 200 ms (p95) | scale | 2 |
| T-BENCH-TMA-01 | bench | TMA Map open < 1.5 s and ≤ 2 MB; hover thumbnail < 150 ms | scale | 3 |
| T-BENCH-CORE-01 | bench | Core open < 1.0 s and ≤ 2 MB; compare 6 cores < 2.5 s at ≥ 55 fps | scale | 3 |
| T-BENCH-URL-01 | bench | Cold URL restore < 4 s; PNG export < 5 s | scale | 5 |

## Traceability matrix

| ID | Tests | Types |
|---|---|---|
| US-1 | T-E2E-US1-01, T-E2E-G4-01, T-BENCH-GENE-01 | e2e, bench |
| US-2 | T-E2E-US2-01, T-E2E-T2-01, T-E2E-C1-01 | e2e |
| US-3 | T-E2E-US3-01, T-E2E-C3-01 | e2e |
| US-4 | T-E2E-US4-01, T-E2E-G6-01, T-WEB-URL-02 | e2e, unit |
| US-5 | T-E2E-US5-01, T-MAN-US5-01 | e2e, manual |
| FR-G1 | T-E2E-G1-01 | e2e |
| FR-G2 | T-E2E-G2-01, T-E2E-G2-02, T-WEB-SEL-01 | e2e, unit |
| FR-G3 | T-E2E-G3-01, T-PIPE-EXPR-01 | e2e, unit |
| FR-G4 | T-E2E-G4-01, T-E2E-G4-02, T-WEB-SEARCH-01 | e2e, unit |
| FR-G5 | T-E2E-G5-01, T-PIPE-PALETTE-01 | e2e, unit |
| FR-G6 | T-E2E-G6-01, T-WEB-URL-01 | e2e, unit |
| FR-G7 | T-E2E-G7-01, T-VIS-EXPORT-01, T-BENCH-URL-01 | e2e, visual, bench |
| FR-U1 | T-E2E-U1-01, T-PIPE-QUANT-01, T-BENCH-FPS-01 | e2e, unit, bench |
| FR-U2 | T-E2E-U2-01, T-BENCH-INTER-01 | e2e, bench |
| FR-U3 | T-E2E-U3-01 | e2e |
| FR-U4 | T-E2E-U4-01, T-WEB-SEL-01 | e2e, unit |
| FR-U5 | T-E2E-U5-01 | e2e (conditional) |
| FR-T1 | T-E2E-T1-01, T-PIPE-CORES-01, T-BENCH-TMA-01 | e2e, unit, bench |
| FR-T2 | T-E2E-T2-01 | e2e |
| FR-T3 | T-E2E-T3-01, T-PIPE-HE-01 | e2e, unit |
| FR-T4 | T-E2E-T4-01 | e2e (conditional) |
| FR-C1 | T-E2E-C1-01, T-PIPE-ALIGN-01, T-VIS-ALIGN-01 | e2e, integration, visual |
| FR-C2 | T-E2E-C2-01, T-PIPE-HE-01 | e2e, unit |
| FR-C3 | T-E2E-C3-01, T-BENCH-CORE-01 | e2e, bench |
| FR-C4 | T-E2E-C4-01 | e2e |
| FR-C5 | T-E2E-C5-01, T-VIS-ALIGN-01 | e2e, visual |
| FR-C6 | T-E2E-C6-01 | e2e (conditional) |
| FR-R1 | T-E2E-R1-01, T-STATIC-REPO-01, T-INT-FRESH-01 | e2e, static, integration |
| FR-R2 | T-PIPE-DATA-01, T-PIPE-CONTRACT-01, T-PIPE-CONTRACT-02, T-PIPE-GUARD-01, T-INT-FRESH-01 | integration, contract, unit |
| FR-P1 | T-E2E-P1-01 | e2e |
| FR-P2 | T-E2E-P2-01 | e2e |
| FR-P3 | T-E2E-P3-01, T-E2E-P3-02, T-E2E-P3-03 | e2e |
| FR-P4 | T-E2E-P4-01 | e2e |
| FR-P5 | T-E2E-P5-01 | e2e |
| FR-P6 | T-E2E-P6-01 | e2e |
| FR-P7 | T-E2E-P7-01 | e2e (conditional) |
| FR-P8 | T-INT-FIG-01 | integration |
| NFR-1 | T-INT-STATIC-01 | integration |
| NFR-2 | T-INT-NGINX-01 | integration |
| NFR-3 | T-BENCH-LOAD-01 | bench |
| NFR-4 | T-BENCH-GENE-01, T-WEB-DECODE-01, T-WEB-LRU-01 | bench, unit |
| NFR-5 | T-BENCH-FPS-01 | bench |
| NFR-6 | T-E2E-XB-01, T-E2E-MOBILE-01 | e2e |
| NFR-7 | T-PIPE-PALETTE-01, T-A11Y-COLOR-01 | unit, a11y |
| NFR-8 | T-PIPE-PRIV-01, T-INT-PUBGUARD-01 | unit, integration |
| NFR-9 | T-STATIC-CITE-01, T-MAN-ZENODO-01 | static, manual |
| NFR-10 | T-A11Y-AXE-01, T-A11Y-KBD-01 | a11y |
| NFR-11 | T-LH-01 | lighthouse |
| NFR-12 | T-E2E-CONSOLE-01 | e2e |
| NFR-13 | T-PIPE-SIZE-01 | integration |
| NFR-14 | T-PIPE-REPRO-01, T-INT-FRESH-01 | integration |
| NFR-15 | T-PIPE-COV-01, T-WEB-COV-01, T-STATIC-TRACE-01 | static |
| NFR-16 | T-WEB-URL-02, T-E2E-NFR16-01 | unit, e2e |

## Coverage rules

- NFR-15 requires ≥ 1 **e2e** test per Must/Should story and FR. Two FRs are end-to-end by nature but not
  browser journeys: FR-R2 is covered by T-INT-FRESH-01 (fresh clone → pipeline → build → full e2e suite on
  the regenerated assets) and FR-P8 by T-INT-FIG-01 (Playwright renders the view URLs of `docs/figures.yaml`).
  NFRs are cross-cutting: they are measured by bench, a11y, Lighthouse and the global e2e fixtures
  (T-E2E-CONSOLE-01, T-A11Y-AXE-01, T-E2E-XB-01). T-STATIC-TRACE-01 reports any gap.
- Budgets are never lowered to pass; a miss goes to `PROGRESS.md` → Decisions needed (CLAUDE.md rule 7).
