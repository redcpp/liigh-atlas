# 02 — The Phase 1 pipeline: raw 10x files → validated canonical dataset → static assets

## What it is

`make pipeline DATASET=<name>` runs `python -m atlas_pipeline run <name>`:

1. **Adapt** (`adapters/`): one adapter per source turns raw files into the canonical tables of
   `docs/DATA_CONTRACT.md`. Every file goes through `rawio.RawFileLog.use()`, which refuses
   `transcripts.*`, `morphology*`, `*.zarr.zip` and records the path; the run prints the list.
2. **Validate** (`contract.py`): pandera schemas + cross-entity invariants; any failure stops the run
   and reports counts, never values.
3. **Persist canonical** to `$DATA_ROOT/canonical/<name>/` (Parquet + `expression.h5ad`).
4. **Build assets** (`assets.py`, `he.py`) into `$DATA_ROOT/build/<name>/_staging`, run the
   quantization and alignment checks, write `manifest.json`, then rename the directory to its
   release id (first 12 hex of the manifest sha256).

`make data TIER=…` (`verify.py`) checks the hand-acquired files: md5 for supplemental files, size vs
`members.txt` for `outs/`; it downloads only what is missing (supplemental by URL, `outs/` members
from the remote ZIP with HTTP range requests, never the full bundle).

## Why this design

- **Adapter boundary**: the lab data (Phase 4) needs one new adapter + config; nothing downstream
  changes. `synthetic-tma` and `scale` are adapters over the ovarian canonical dataset.
- **Dev UMAP** (Gate 0): kNN cluster coherence, 15 neighbours, scored on the 406,611 cells both
  embeddings cover. Provided Xenium UMAP 0.791 vs seeded scanpy recompute 0.692 → the provided one is
  used. The recompute is cached in `$DATA_ROOT/derived/ovarian-10x/umap-<key>.parquet` with a JSON
  sidecar (parameters, library versions, sha256 of the input matrix); later runs log "cache hit".
- **Cells without an embedding** (Gate 1): 513 cells with 0 transcripts are missing from the 10x Cell
  Groups CSV and the provided UMAP. No position is invented: they keep their real centroids (spatial
  views), go to 10x's own `Unassigned` group, and carry `has_umap = false` with NaN UMAP coordinates.
  In `cells/umap.u16` they are the sentinel 65535; the manifest reports `counts.cells_without_umap`
  (for Methods). This is a contract rule for every adapter — the lab data will have QC-filtered cells
  without an embedding.
- **Quantized coordinates** (ADR-0002): uint16 with offset + scale, spatial per section, UMAP per
  axis. Worst case 0.088 µm for the 11.5 mm dev section; the build fails above 0.5 µm or 0.1% of the
  UMAP range.
- **Expression** (ADR-0003): one file per gene, sparse (LEB128 delta indices + uint8) or dense,
  whichever is smaller; 0 means "not detected", so detected values are clamped to ≥ 1.
- **H&E** (ADR-0004, ADR-0009): warped once into the µm frame with Lanczos at 0.270 µm/px (source
  0.274), 512 px WebP tiles, level 0 = coarsest. The source affine and pixel size are in
  `sections.json`. The source is 43,993 × 30,918 px (above OpenCV's 32,767 px limit), so the warp
  always runs in blocks whose source windows overlap by ≥ 8 px; T-PIPE-HE-02 shows a tiled warp equals
  a single-pass warp. When an output pixel spans ~2+ source pixels, an exact box average on a
  grid-aligned window runs first, so neighbouring blocks agree.
- **Readers** (ADR-0009): direct `pyarrow`/`h5py`/`tifffile` readers behind the open-guard, gated on
  tested `analysis_sw_version` values; spatialdata-io is a test-only oracle that must agree on cell
  ids, centroids and matrix shape.
- **Alignment test** (Gate 1): two tissue definitions for the random points — the brightfield mask
  (block-averaged gray < 220) and an image-independent one (within 20 µm of any cell centroid). The
  centroids must pass (p < 1e-6, d ≥ 0.8) under both; the same centroids shifted 25 µm must fail
  under both. Four comparisons printed per test.
- **Determinism**: seeded RNGs, sorted JSON with fixed float formatting, no timestamps in assets,
  deterministic WebP settings. Two runs give identical hashes (`make repro`).

## Re-derive µm → H&E pixels by hand (the Phase 1 gate)

The 10x alignment CSV `A` maps H&E px → Xenium px. Xenium px = µm / 0.2125
(`experiment.xenium: pixel_size`). So H&E px = `inverse(A) · [x/0.2125, y/0.2125, 1]`.

```
A        = [[ 0.010909,  1.289525,  -721.007],      inverse(A) = [[ 0.006560, -0.775424, 29969.186],
            [-1.289525,  0.010909, 38642.678],                    [ 0.775424,  0.006560,   305.602],
            [ 0,         0,            1     ]]                   [ 0,         0,            1     ]]
```

| cell_id | x, y (µm) | Xenium px | H&E px (u, v) |
|---|---|---|---|
| aaaaebmm-1 | 540.865, 4230.247 | 2545.25, 19907.05 | 14549.48, 2409.83 |
| hbpkfdbb-1 | 9753.912, 4040.316 | 45900.76, 19013.25 | 15526.95, 36022.87 |
| oijbekda-1 | 9288.425, 6790.256 | 43710.23, 31954.15 | 5477.90, 34409.17 |

Check the first row: u = 0.006560·2545.25 − 0.775424·19907.05 + 29969.186 ≈ 14549.5. The ~90°
rotation shows up as Xenium x driving H&E v. One H&E pixel is √|det A| · 0.2125 = 1.2896 · 0.2125 ≈
0.274 µm.

## How to verify by hand

1. `make data TIER=meta,core,he` → table with `0 downloaded, 0 failed`.
2. `make pipeline DATASET=ovarian-10x` → `cells = 407124`, `median transcripts per cell = 178`,
   18 clusters, the files-opened list ends with `forbidden …: NONE`.
3. Open `$DATA_ROOT/build/ovarian-10x/<release>/he/S1/S1-region/3/…webp` in Preview: tissue, axis-aligned
   with the Xenium frame (not rotated).
4. The alignment block prints four comparisons per test: centroids d ≈ 1.34–1.38 under both tissue
   definitions ("passes the rule"); the 25 µm-shifted control d ≈ 0.24–0.26 ("fails the rule").
5. `make repro DATASET=fixture` (seconds) or `DATASET=ovarian-10x` (≈ 5 min) prints `IDENTICAL`.
