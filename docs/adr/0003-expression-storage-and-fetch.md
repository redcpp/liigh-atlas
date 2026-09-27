# ADR-0003 — Expression storage and fetch strategy

Status: Proposed (maintainer gate after Phase 0)

## Context

NFR-4: gene switch p95 < 300 ms over 50 random genes, cold per-gene cache, local static server. The
dev matrix has 80.5M non-zero entries over 5,101 genes and 407K cells (measured from
`experiment.xenium`), i.e. ~15.8K non-zeros per gene on average (~3.9% density); lab data is similar
(~443K cells, ~5K genes). Only one or two genes are shown at a time.

## Options

1. **Dense matrix chunks by gene block** (Zarr-like, e.g. 64 genes × all cells): one request may serve
   neighbors, but each switch downloads 64 × 0.44 MB ≈ 28 MB. Fails NFR-4 on slow links.
2. **One file per gene, dense uint8**: 0.44 MB per gene, 2.2 GB total; simple but 10× larger than needed.
3. **One file per gene, sparse or dense uint8, whichever is smaller**: sparse = delta-encoded cell
   indices (LEB128 varint, ~2 B) + uint8 value per non-zero ≈ 3 B/nnz; dense = 1 B/cell. Break-even at
   ~33% density; average gene ≈ 47 KB, worst case 0.44 MB.
4. **Packed shards + HTTP range requests**: same per-gene encoding concatenated into ~64 shard files
   with an offset index; one range request per gene. Fewer files, but no transport compression on
   ranges and more fragile caching.

## Decision

**Option 3 by default: `expr/<gene_id>.bin`, per-gene sparse-or-dense uint8, precompressed `.gz`;
option 4 (packed shards) as a build flag** if the LIIGH host limits file counts (Q13).

- Values: display-normalized `log1p(CP10k)` (DATA_CONTRACT §3), quantized per gene to `uint8` with
  `max_v` in `genes.json` for the color bar; 0 is reserved for "not detected".
- Header: 1-byte format (`0` dense, `1` sparse), `uint32` nnz, then payload.
- Estimated total ≈ 80.5M × 3 B ≈ 240 MB raw (≈ 260 MB at 443K), well inside NFR-13.
- Fetch path: autocomplete highlight prefetches the top suggestion; selection fetches through the Web
  Worker with `AbortController` (a newer selection cancels the older), decodes into the shared color
  attribute and posts back one `Uint8Array` (transferable). LRU cache of 64 genes (≤ 28 MB worst case).

**Budget sketch (worst case dense gene, cold cache, local server):** fetch 0.44 MB ≈ 10–30 ms + decode
443K ≈ 5 ms + color attribute upload ≈ 5 ms + one frame 16 ms → ≈ 60 ms, leaving 5× headroom for p95
under 300 ms. Measured by `make bench` (ADR-0007).

## Consequences

- ~5.1K small files per release; nginx serves them trivially, but copying uses `rsync`, and the file
  count is a question for Jair (Q13).
- Per-gene files are cacheable independently and survive releases only if unchanged (content hashes in
  the manifest make that visible).
- Co-expression views (two genes) are two fetches; allowed, not optimized.

**Building block:** caching (client LRU + immutable HTTP cache) over sharded/partitioned object storage.
