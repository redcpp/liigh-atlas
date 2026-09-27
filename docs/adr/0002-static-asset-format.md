# ADR-0002 — Static asset format

Status: Accepted with conditions (Gate 0, `[Diego]`)

## Context

The web app reads only static files (NFR-1). Constraints: < 5 MB before first interaction (NFR-3),
byte-identical rebuilds (NFR-14), ≤ ~5 GB total (NFR-13), and releases that stay addressable for cited
URLs (NFR-16). BRIEF §8 suggests `float32` coordinates; at 443K cells one float32 embedding is
443K × 2 × 4 B = 3.54 MB, which alone uses 71% of NFR-3 before JavaScript, cluster ids and metadata.

## Options

1. **One container file** (Arrow IPC / Parquet in the browser): one decoder, but a large WASM/JS
   reader in the initial payload and no per-column lazy loading without range logic.
2. **AnnData-Zarr / SpatialData-Zarr**: ecosystem standard; many small chunk files, JSON metadata
   round-trips, float32 coordinates, and a Zarr reader in the bundle.
3. **Typed binary arrays + JSON manifest** (BRIEF default): one little-endian file per column, fetched
   with `fetch().arrayBuffer()` and viewed as a TypedArray with zero parsing.
4. Option 3 with **quantized coordinates** (`uint16` + per-axis offset and scale in the manifest).

## Decision

**Option 4: typed little-endian binary columns + a JSON manifest, with uint16-quantized coordinates.**
This deviates from the BRIEF `float32` default, justified by the numbers:

| Array | float32 | uint16 | Precision of uint16 |
|---|---|---|---|
| UMAP (443K × 2) | 3.54 MB | 1.77 MB | range/65,535 ≈ 0.0006 units for a ~40-unit embedding; sub-pixel even at 16× zoom on a 4K screen |
| Spatial per section (443K × 2) | 3.54 MB | 1.77 MB | 22,500 µm / 65,535 ≈ 0.34 µm (TMA slide) — below the 0.2125 µm × 2 pixel pitch that matters for ~10 µm cells |

**Gate 0 conditions:** (a) spatial coordinates are quantized **per section**, UMAP per axis, each with
its own `offset` and `scale` in the manifest (`v = offset + q · scale`); (b) T-PIPE-QUANT-01 asserts the
maximum round-trip error is ≤ 0.5 µm (spatial) and ≤ 0.1% of the embedding range (UMAP), and the build
fails otherwise; (c) URL state and figure exports always use physical units (µm, UMAP units), never
quantized integers, so a rebuild with a different scale cannot change a cited URL (NFR-16, T-WEB-URL-03).

Initial payload estimate: 1.77 (UMAP) + 0.44 (cluster `uint8`) + ~0.2 (manifest, tables,
gene index) + ~0.6 (JS/CSS, compressed) ≈ **3.0 MB** < 5 MB.

**Layout per release:** `data/<dataset>/<release>/` with `manifest.json` (schema version, dataset
record, per-file `{path, dtype, shape, bytes, sha256, scale, offset}`), `cells/*.u8|u16`,
`genes.json`, `clusters.json`, `cores.json`, `sections.json`, `expr/` (ADR-0003), `he/` (ADR-0004).
`<release>` is the first 12 hex chars of the manifest's sha256, so a release directory is immutable and
cacheable forever (ADR-0006). `releases.json` (not cached) maps dataset → current and past releases.

**Ordering:** cells sorted by section → core → Morton code of (x, y); each core is a contiguous index
range, so Core Detail slices arrays without an index lookup.

**Compression:** transport compression by the server (precompressed `.gz` via `gzip_static`); files
themselves stay raw so the browser can view them without a decoder. **Determinism:** sorted keys in
JSON, fixed float formatting, pinned encoders, no timestamps in outputs.

## Consequences

- The web decoder is ~50 lines: `new Uint16Array(buf)` + offset/scale in the worker; integers never
  leave the data layer.
- Quantization error is bounded and tested; float32 remains a manifest option (`dtype`) if a lab
  embedding needs it, at the cost of NFR-3 headroom.
- No external tool can open the assets directly; the canonical dataset remains the interoperable form.

**Building block:** static object storage with content-addressed (hash-named) immutable blobs and a manifest index.
