# PROGRESS

Running log. Updated at the end of every agent turn (CLAUDE.md rule 8). No dates except the final
deadline (~March 2027).

## Phase

**Phase 1 — foundation + pipeline on development data** (goal `g1-pipeline`, branch `phase-1-pipeline`).
All exit criteria in `docs/ROADMAP.md` met on the dev data; waiting for the maintainer gate
(re-derive µm → H&E px for 3 cells, read `docs/learn/02-pipeline.md`).

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
  0 differing.
- Tests: 53 pytest tests (data-marked ones skip without `$DATA_ROOT`), pipeline coverage 92% with
  data, 87% without (CI); vitest scaffold test; ruff, mypy strict, eslint, tsc clean.
- Docs: ADR-0009 (direct Xenium readers + OpenCV Lanczos, *Proposed*), `docs/learn/02-pipeline.md`,
  DATA_CONTRACT §10 (Phase 1 notes).

## Findings worth a look at the gate

1. **513 zero-transcript cells** are missing from the 10x Cell Groups CSV and the provided UMAP. Kept
   (10x counts them in 407,124), labelled `Unassigned` (10x's own group), placed at that group's UMAP
   median. Alternative: drop them and change the expected count — not done, it contradicts the 10x
   metrics check.
2. **Alignment test design fix.** First fixture run used an Otsu tissue mask; on a crop with no
   background Otsu split nuclei from stroma, biasing the random points. Replaced by a fixed
   brightfield background threshold (block-averaged gray < 220 at ~10 µm/px). The pass criteria
   were not changed.
3. **Fixture** is a 600 µm window of the dev data with its H&E crop (not a subset of
   `synthetic-tma`), so CI can run the H&E and alignment tests. Reason in DATA_CONTRACT §10.
4. **synthetic-tma / scale have no H&E yet**: synthetic cores are moved onto a TMA grid, so they need
   a per-core source offset (Phase 3 scope).
5. **Scale sub-cluster colours** are a darker shade of the parent — placeholder until the NFR-7
   palette (T-PIPE-PALETTE-01, Phase 2).
6. Precompressed `.gz` assets (ADR-0002/0003) are left to `make build` (Phase 6).

## Next

1. Maintainer gate: re-derive µm → H&E px for 3 cells (table in `docs/learn/02-pipeline.md`),
   review ADR-0009.
2. Phase 2 (`g2-umap`): web data layer, state/URL codec, UMAP Atlas, palette, e2e + bench.

## Blockers

- None for Phase 2. Phase 4 waits on the lab handoff (meeting agenda group 1). Deployment details wait
  on Jair (Q8, Q13). A public repo/demo waits on Dany (Q10).

## Decisions needed

1. **ADR-0009** (read Xenium files directly instead of spatialdata-io; OpenCV for Lanczos): Proposed.
2. Carried over: ADR-0001, ADR-0003, ADR-0005, ADR-0006, ADR-0007, ADR-0008 still *Proposed*.
3. Zero-transcript cells (finding 1): keep as done, or drop them?

## Verification (last run)

See the transcript of this turn: `make setup`, `make data TIER=meta,core,he`,
`make pipeline DATASET=ovarian-10x|synthetic-tma|scale`, `make repro DATASET=ovarian-10x`,
`make test`, `make verify`, `git ls-files` check, `du -sh`.

## Measured numbers (dev data, spinning-disk external drive)

| Dataset | Cells | Genes | Clusters | Sections / cores / patients | Assets | Build time |
|---|---|---|---|---|---|---|
| ovarian-10x | 407,124 (median 178 tx) | 5,101 | 18 | 1 / 1 region / 1 | 402.3 MB (11,766 files) | ≈ 2.5 min |
| synthetic-tma | 174,841 | 5,101 | 18 | 3 / 38 / 27 | 75.3 MB | 24 s |
| scale | 447,694 | 5,101 | 23 | 3 / 100 / 62 | 181.4 MB | 45 s |
