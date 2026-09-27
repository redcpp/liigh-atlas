# ADR-0005 — State management and versioned URL schema

Status: Proposed (maintainer gate after Phase 0)

## Context

FR-G6: full view state in the URL, shareable and citable. NFR-16: URLs printed in the paper must keep
resolving after future releases — of the app and of the data. Views are linked (FR-G2), so state is
shared, not per component. Selections can contain hundreds of thousands of cells.

## Options

**Store:** (1) React context + reducers; (2) Redux Toolkit; (3) **Zustand**: one small store, selector
subscriptions, usable outside React (the worker bridge and URL codec).

**URL encoding:**
- a. Serialized JSON (base64) in the hash: complete but opaque, long, and tied to internal shapes.
- b. **Explicit query parameters with a version field**, parsed by a per-version codec, with
  migrations `v1 → v2 → …`.
- c. Short links resolved by a server: breaks NFR-1.

**Selections in the URL:** list of cell IDs (unbounded) vs **the selection's definition** (cluster,
core, patient, or lasso polygon in UMAP coordinates), recomputed deterministically on load.

## Decision

**Zustand store + versioned query-parameter URLs (option b), with selections stored by definition.**

```
/?v=1&ds=ovarian-10x&r=3fa1c09b2e7d&view=core&cores=C012,C044&color=gene:ENSG00000119888
  &hide=c07,c19&sel=lasso:<x1>_<y1>~<x2>_<y2>~…&op=0.6&cam=<x_um>,<y_um>,<zoom>
```

- `v` is the URL schema version; `r` pins the **data release** (manifest hash, ADR-0002). A cited URL
  therefore names both the code contract and the exact data it showed.
- Genes are referenced by `gene_id`, clusters by stable `cluster_id`, cores by `core_id` — never by
  array index, so re-ordering in a new release does not change meaning.
- Unknown parameters are ignored with a console-free notice; missing ones take defaults.
- If `r` is no longer the current release, the app loads that release if it is still hosted (NFR-2
  keeps the previous release); otherwise it opens the current release and shows "This link was made
  with release r; showing the current release".
- **Physical units only** (Gate 0): camera centers are in µm (spatial views) or UMAP units (UMAP view),
  lasso vertices in UMAP units, all as fixed-precision decimals (3 decimals UMAP, 0.1 µm spatial).
  Asset-level quantized integers never appear in a URL (ADR-0002, T-WEB-URL-03).
- Lasso polygons: ≤ 64 vertices; URL length target ≤ 2,000 characters (checked in tests).
- History: camera changes use `replaceState` (debounced 250 ms); view, gene, core and selection
  changes use `pushState`, so Back behaves as users expect.
- **Fixtures:** `fixtures/urls/v1/*.json` hold URL → expected state pairs; every future release must
  parse them to the same state (NFR-16 regression tests). Changing the schema requires `v=2`, a
  migration from v1 and new fixtures, never editing old ones.

## Consequences

- The URL codec is the most tested module (unit round-trip over random states + fixtures + e2e).
- Hosting must keep at least the previous release on disk (quota ≥ 10 GB, ADR-0006).
- Readable URLs are longer than short links, but work without any server.

**Building block:** API versioning / backward-compatible schema evolution (client-side state serialization).
