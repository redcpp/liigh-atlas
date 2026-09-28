# PROGRESS

Running log. Updated at the end of every agent turn (CLAUDE.md rule 8). No dates except the final
deadline (~March 2027).

## Phase

**Phase 1 — foundation + pipeline on development data** (goal `g1-pipeline`, branch `phase-1-pipeline`).
All exit criteria in `docs/ROADMAP.md` met on the dev data. **Gate 1 closed** (`[Diego]`); Phase 2 not
started (waits for the maintainer to start `g2-umap`).

## Gate 1 closed (`[Diego]`)

1. Oracle accepted: `cells.zarr.zip` is a test-only input. Without it, T-PIPE-ORACLE-01 skips with an
   explicit reason (pytest `-ra` prints it in `make verify`); `test_oracle_skip.py` covers the rule.
2. Phase 4 safety: ROADMAP Phase 4 exit criterion 7 — the lab's `analysis_sw_version` enters the
   allowlist only after the oracle passes on the lab data. Meeting agenda Q2 adds `cells.zarr.zip` per
   section (test-only, ~460 MB total `[Assumption]`) to the handoff checklist. BRIEF.md unchanged.


## Done

- Monorepo scaffolding: `pipeline/` (package `atlas_pipeline`), `web/` (Vite + React + TS strict,
  eslint, prettier, vitest; scaffolding only), `scripts/check_repo.py`, `fixtures/fixture/`,
  `.github/workflows/verify.yml`, `.githooks/pre-commit`, `Makefile`.
- `make data`: md5 for supplemental, size vs `members.txt` for `outs/`, downloads only what is
  missing (HTTP range extraction of single ZIP members). Idempotent: 13 files checked, 0 downloaded.
- Open-guard + raw-file log: every run prints the files it opened; none is `transcripts.*`,
  `morphology*` or `*.zarr.zip`.
- Adapters `ovarian-10x`, `synthetic-tma`, `scale`, `fixture`; pandera + cross-entity validation
  (27 checks) with config totals.
- Dev UMAP selection (T-PIPE-UMAP-01): provided 0.7911 vs recomputed 0.6919 → provided; recompute
  cached in `$DATA_ROOT/derived/ovarian-10x/` and reused ("cache hit").
- Assets: uint16 quantized coordinates (T-PIPE-QUANT-01: 0.088 µm spatial, 7.6e-6 of UMAP range),
  per-gene sparse/dense uint8 expression, JSON tables, Merkle-style manifest, release = sha256[:12].
- H&E pyramid (ADR-0004 conditions): Lanczos4 at 0.270 µm/px (source 0.274), 8 levels, 6,652 WebP
  tiles; source affine + source pixel size in `sections.json`.
- Alignment: T-PIPE-ALIGN-01 d = 1.379, p = 5.1e-177; T-PIPE-ALIGN-02 d = 1.361, p = 1.1e-173;
  negative control (25 µm shift) d ≈ 0.26. Criteria fixed before the first run: p < 1e-6, d ≥ 0.8.
- Reproducibility (T-PIPE-REPRO-01): two ovarian-10x runs → release `681e291a3964`, 11,767 files,
  0 differing; re-run after Gate 1 → release `77b97a69f5a1`, 11,767 files, 0 differing.
- Tests: 65 pytest tests (data-marked ones skip without `$DATA_ROOT`), pipeline coverage 92.75% with
  data, 87% without (CI); vitest scaffold test; ruff, mypy strict, eslint, tsc clean.
- Docs: ADR-0009 (direct Xenium readers + OpenCV Lanczos, *Proposed*), `docs/learn/02-pipeline.md`,
  DATA_CONTRACT §10 (Phase 1 notes).

## Gate 1 applied (`[Diego]`)

1. **Cells without an embedding**: no invented UMAP positions. `has_umap` (bool) added to `cells`;
   NaN UMAP when false; kept in the canonical dataset (407,124) and the spatial views; sentinel 65535
   in `cells/umap.u16`; `counts.cells_without_umap` in the manifest (ovarian-10x 513, synthetic-tma
   162, scale 472). General rule in DATA_CONTRACT §1/§8; AC-FR-U1.1 counts "all cells that have an
   embedding"; new AC-FR-P1.2 (Methods reports the count); PRD changelog 0.3. Test T-PIPE-UMAP-02.
2. **Alignment**: second, image-independent tissue definition (≤ 20 µm from a cell centroid). Pass
   rule required under both; the 25 µm-shifted control must fail under both. On ovarian-10x, raw:
   centroids d = 1.379 / 1.348, control d = 0.258 / 0.242; pyramid: centroids d = 1.359 / 1.333,
   control d = 0.262 / 0.248 (brightfield / near-cell). All four printed per test.
3. **UMAP choice** approved; unchanged.
4. **ADR-0009 accepted with conditions**: (a) `analysis_sw_version` gate (`xenium-3.0.0.15` only,
   T-PIPE-XVER-01); (b) spatialdata-io 0.7.1 as a dev-only oracle (T-PIPE-ORACLE-01) — it needs
   `cells.zarr.zip` for the table, so the *test* reads it (the pipeline never does); the test asserts
   no `transcripts.*`/`morphology*` opened; (c) blockwise warp with ≥ 8 px overlap (scaled by the
   shrink factor), grid-aligned box pre-shrink, seam test T-PIPE-HE-02 (tiled vs single pass, ≤ 2 levels,
   fixed before the run). The first run failed on the box-shrink path (max 4 levels, mean 0.004):
   `cv2.warpAffine` rounds each call's translation to 1/32 px separately. Fixed by computing fixed-point
   coordinates from the global pixel position and using `cv2.remap`; now max difference 0 on both paths.
   Tolerance unchanged.
5. **Q13** now carries the measured dev build (11,767 files, 402.3 MB) and a projected lab TMA build
   (≈ 13,800 files / ≈ 0.5 GB at 100 cores; ≈ 18,200 at 150).

Also: `make fixture` is now byte-deterministic (fixed OME UUID derived from the window).

## Open findings (carried)

1. **Fixture** is a 600 µm window of the dev data with its H&E crop (not a subset of `synthetic-tma`),
   so CI runs the H&E and alignment tests (DATA_CONTRACT §10).
2. **synthetic-tma / scale have no H&E yet** (per-core source offset needed; Phase 3).
3. **Scale sub-cluster colours** are placeholders until T-PIPE-PALETTE-01 (Phase 2).
4. Precompressed `.gz` assets are left to `make build` (Phase 6).

## Next

1. Maintainer gate: re-derive µm → H&E px for 3 cells (table in `docs/learn/02-pipeline.md`),
   review ADR-0009.
2. Phase 2 (`g2-umap`): web data layer, state/URL codec, UMAP Atlas, palette, e2e + bench.

## Blockers

- None for Phase 2. Phase 4 waits on the lab handoff (meeting agenda group 1). Deployment details wait
  on Jair (Q8, Q13). A public repo/demo waits on Dany (Q10).

## Decisions needed

1. Carried over: ADR-0001, ADR-0003, ADR-0005, ADR-0006, ADR-0007, ADR-0008 still *Proposed*.

## Verification (last run)

See the transcript of the Gate 1 close turn: `make verify` and `uv run python scripts/check_docs.py`
(full output), plus the oracle skip shown on a `$DATA_ROOT` without `cells.zarr.zip`.

## Measured numbers (dev data, spinning-disk external drive)

| Dataset | Cells | Genes | Clusters | Sections / cores / patients | Assets | Build time |
|---|---|---|---|---|---|---|
| ovarian-10x | 407,124 (median 178 tx; 513 without UMAP) | 5,101 | 18 | 1 / 1 region / 1 | 402.3 MB (11,767 files incl. manifest) | ≈ 3.7 min |
| synthetic-tma | 174,841 (162 without UMAP) | 5,101 | 18 | 3 / 38 / 27 | 75.3 MB | 26 s |
| scale | 447,694 (472 without UMAP) | 5,101 | 23 | 3 / 100 / 62 | 181.4 MB | 38 s |
