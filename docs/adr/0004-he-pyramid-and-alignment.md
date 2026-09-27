# ADR-0004 — H&E pyramid format and alignment

Status: Proposed (maintainer gate after Phase 0)

## Context

Core Detail shows H&E next to (and under) cells with synchronized pan/zoom down to single-cell level
(FR-C1, FR-C2, FR-C5). The dev H&E is a 3.58 GB OME-TIFF; its alignment CSV is a 3×3 affine that maps
H&E pixels to Xenium pixels, with a ~90° rotation and scale ≈ 1.29 (measured), so an H&E pixel is
≈ 0.274 µm. Cells are in µm. The core-open budget is < 1 s p95 and ≤ 2 MB (TECH_SPEC §7).

## Options

**Format**
1. Serve the OME-TIFF (or OME-Zarr) and decode in the browser (Viv/geotiff.js): no preprocessing, but
   raw or LZW tiles are large, and the decoder adds bundle weight.
2. **Pre-rendered 512 px WebP tile pyramid** (`{z}/{x}_{y}.webp`, quality 85): native browser decode,
   ~25–35% smaller than JPEG at equal quality, all target browsers support it.
3. JPEG tile pyramid: most compatible, larger.

**Alignment**
A. Keep native H&E pixels and apply the affine at render time (deck.gl `modelMatrix`): no resampling,
   but rotated tile culling and picking get subtle, and every consumer (export, thumbnails) must repeat it.
B. **Warp once, offline, into the section's µm frame**: tiles are axis-aligned with cell coordinates,
   one resampling (bilinear) at native H&E resolution.

## Decision

**Option 2 + B: the pipeline warps the H&E into the section µm frame at ≈ native resolution
(0.274 µm/px for dev data), crops per core (bbox + 50 µm margin), and writes a 512 px WebP pyramid per
core plus a low-resolution section overview and a 256 px thumbnail per core (FR-T3).**

- Transform chain (DATA_CONTRACT §6): µm → Xenium px (÷ 0.2125) → H&E px via `inverse(A_align)`.
  Direction is verified, not trusted: the Phase 1 test compares hematoxylin intensity (color
  deconvolution) at 1,000 cell centroids against 1,000 random in-tissue points and must show a
  significant, large effect; a wrong direction or transpose fails it.
- Reading uses `tifffile` on pyramid levels with bounded memory (window reads), never the whole image.
- Size estimate: lab TMA ≈ 100 cores × (1.1 mm / 0.274 µm)² ≈ 1.6 Gpx; at ~0.15 B/px WebP ≈ 0.25 GB,
  plus overview levels ≈ 0.35 GB; dev whole tissue ≈ 1.2 Gpx ≈ 0.3 GB. Inside NFR-13.
- Core open fetches ≈ 6–12 tiles of 30–60 KB at the fitting zoom ≈ 0.5 MB, within the 2 MB budget.
- WebP encoding is pinned (Pillow/libwebp version in the lockfile) for byte-identical rebuilds.

## Consequences

- Rendering is a plain `TileLayer` + `BitmapLayer` in µm coordinates; synchronized pan/zoom and
  overlays share one camera, and PNG export needs no transform logic.
- One-time resampling costs a little sharpness (bilinear at native resolution); acceptable for display,
  the raw OME-TIFF remains the scientific source.
- If lab H&E is not aligned (Q3), registration (landmarks or intensity-based) becomes a Phase 4 task
  that only produces a new `affine`; nothing else changes.

**Building block:** tiling (image pyramid) served from static object storage with CDN-style caching.
