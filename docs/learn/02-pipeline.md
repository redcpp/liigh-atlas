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
- **513 cells with 0 transcripts** are missing from the 10x Cell Groups CSV and from the provided
  UMAP. They go to 10x's own `Unassigned` group (no invented label) and sit at the median UMAP
  position of that group; the count is in `dataset.provenance.umap`.
- **Quantized coordinates** (ADR-0002): uint16 with offset + scale, spatial per section, UMAP per
  axis. Worst case 0.088 µm for the 11.5 mm dev section; the build fails above 0.5 µm or 0.1% of the
  UMAP range.
- **Expression** (ADR-0003): one file per gene, sparse (LEB128 delta indices + uint8) or dense,
  whichever is smaller; 0 means "not detected", so detected values are clamped to ≥ 1.
- **H&E** (ADR-0004, ADR-0009): warped once into the µm frame with Lanczos at 0.270 µm/px (source
  0.274), 512 px WebP tiles, level 0 = coarsest. The source affine and pixel size are in
  `sections.json`.
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
4. The alignment lines report Cohen's d ≈ 1.4 (raw) and ≈ 1.4 (pyramid); the negative control
   (centroids shifted 25 µm) drops to ≈ 0.26.
5. `make repro DATASET=fixture` (seconds) or `DATASET=ovarian-10x` (≈ 5 min) prints `IDENTICAL`.
