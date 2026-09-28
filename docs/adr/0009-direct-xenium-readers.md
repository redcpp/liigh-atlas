# ADR-0009 — Read Xenium outputs directly (no spatialdata-io); OpenCV for the H&E warp

Status: Accepted with conditions (Gate 1, `[Diego]`)

## Context

BRIEF §8 lists `spatialdata-io` as a default pipeline library. The pipeline must never open
`transcripts.*`, `morphology*` or `*.zarr.zip` (BRIEF §4.2) and must log every raw file it opens
(T-PIPE-GUARD-01). The H&E warp (ADR-0004) needs a windowed Lanczos resampler that is fast on
1.2 Gpx and deterministic.

## Options

1. **`spatialdata_io.xenium()`**: one call, ecosystem objects. By default it also reads transcripts
   and morphology images; switching those off relies on flags per version, and the files it opens
   are not visible to our open-guard. Adds dask, xarray, spatialdata and their pins.
2. **Direct readers**: `pyarrow` for `cells.parquet`, `h5py` for `cell_feature_matrix.h5`, `json`
   for `gene_panel.json`/`experiment.xenium`, `tifffile` + `zarr` for windowed OME-TIFF reads.
   Every open goes through `rawio.RawFileLog.use()`.
3. H&E resampling with `scikit-image.warp` (order 3, no Lanczos) vs **OpenCV `warpAffine`
   (`INTER_LANCZOS4`)**, C++, multi-threaded, identical output for identical input.

## Decision

**Option 2 + OpenCV (`opencv-python-headless`).** Measured on the dev data: adapter load ≈ 5 s,
full ovarian-10x build ≈ 2.5 min including the 8-level pyramid (42,852 × 29,849 px at 0.270 µm/px).
`anndata`, `scanpy`, `pandas`, `pyarrow`, `zarr` stay as in BRIEF §8.

**Gate 1 conditions:**
(a) the adapter reads `analysis_sw_version` from `experiment.xenium` and accepts only tested
versions (`atlas_pipeline.xenium.SUPPORTED_ANALYSIS_VERSIONS`, today `xenium-3.0.0.15`); any other
fails loudly (T-PIPE-XVER-01). (b) spatialdata-io is a **test-only oracle** (dev dependency;
transcripts, images, labels and boundaries off): cell ids, centroids and matrix shape must match our
reader on the dev data (T-PIPE-ORACLE-01). spatialdata-io 0.7.1 cannot build the table without
`cells.zarr.zip`, so the oracle reads it; the pipeline never does, and the test asserts the oracle opens
no `transcripts.*` or `morphology*`. (c) The dev H&E is 43,993 × 30,918 px, above OpenCV's 32,767 px
per side, so the builder always warps in blocks (2,048 output px) whose source windows overlap by
≥ 8 px (scaled by the shrink factor); the pre-shrink is an exact box average on a grid-aligned window.
Lanczos4 runs through `cv2.remap` with fixed-point coordinates computed from each pixel's global
position, because `cv2.warpAffine` rounds each call's translation on its own (a 4-level seam in the first
T-PIPE-HE-02 run). T-PIPE-HE-02 now finds tiled and single-pass warps identical (max difference 0).

## Consequences

- The guard sees every file; the log proves no forbidden file was opened.
- The lab adapter (Phase 4) reuses the same readers for standard Xenium `outs/`; if the lab hands a
  SpatialData object instead, a thin adapter can read it without changing downstream code.
- OpenCV's Lanczos kernel does not anti-alias, so the builder pre-shrinks with area averaging when
  the output pixel is > 1.25× the source pixel (`he.render`).

**Building block:** batch ETL pipeline (audited extract, transform, load into immutable object storage).
