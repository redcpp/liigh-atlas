# ADR-0001 — Build vs adopt the viewer

Status: Proposed (maintainer gate after Phase 0)

## Context

The atlas needs three linked views over ~443K cells: UMAP Atlas, TMA Map (sections with cores at real
positions, click to open) and Core Detail (H&E + cells, several cores side by side). Everything must be
static (NFR-1) and every view must be a short, versioned URL that still resolves after later releases,
because it will be printed in figure legends. Open-source spatial single-cell viewers exist; adopting
one could save months, or could lock the requirements that matter most into someone else's model.

## Options

| Criterion | A. Vitessce as the whole app | B. Custom app + Viv for H&E | C. Custom React + deck.gl app |
|---|---|---|---|
| **FR-T1** TMA Map, cores at real positions, click → detail | No built-in TMA/core view; needs a custom plugin view plus config rewriting to open a core | Custom view | Custom view (a `PolygonLayer` of cores over a section overview) |
| **FR-C3** compare N cores side by side | N spatial views declared in the config; adding a core at runtime = generating a new config | Custom grid of synchronized deck.gl views | Same as B |
| **FR-G6** full state in URL | State is the Vitessce config + coordination values; shareable as a hosted or URL-encoded config, long and not shaped by us | Our own compact codec | Our own compact codec |
| **NFR-16** cited URLs survive releases | Cited links depend on Vitessce's config schema and upgrade path; pinning a version freezes the app | We own the URL schema and its migrations | Same as B |
| NFR-3 / NFR-4 initial load, gene switch | Reads AnnData-Zarr/OME formats; payload shaped by the framework | Our formats (ADR-0002/0003) | Our formats (ADR-0002/0003) |
| H&E rendering | Viv (multichannel OME-TIFF/Zarr) | Viv loaders on an RGB pyramid; heavier than needed | deck.gl `TileLayer` + `BitmapLayer` over WebP tiles (ADR-0004) |
| Effort / risk | Lowest to a first demo; highest for the TMA and URL requirements | Medium; extra dependency for one layer | Highest up-front; everything is ours to test |

Also considered: CZ CELLxGENE Explorer (needs a server process: breaks NFR-1) and TissUUmaps
(strong for image + marker overlays, but no UMAP ↔ tissue linking model or TMA navigation matching
FR-T1/FR-C3). Squidpy/napari are desktop tools, not websites.

## Decision

**Build a custom React + TypeScript + deck.gl app (option C); do not adopt a viewer framework or Viv.**

The four deciding requirements (FR-T1, FR-C3, FR-G6, NFR-16) are exactly where a framework's model
would have to be bent or wrapped; NFR-16 in particular makes the URL schema a long-lived public
contract that we must own and migrate ourselves. deck.gl already gives the hard part (WebGL rendering
of 443K instanced points, tiling, picking, multiple views) as a library, not a framework. Viv is
designed for multichannel fluorescence images; our H&E is RGB and is pre-tiled to WebP, which deck.gl's
`TileLayer` renders directly.

## Consequences

- We write and test the views, linking, state and URL codec (Phases 2, 3, 5); TEST_PLAN covers them.
- The canonical dataset (DATA_CONTRACT) stays framework-neutral: exporting AnnData-Zarr for Vitessce
  later is a pipeline add-on (Could), not a rewrite.
- Revisit if Phase 2 misses NFR-5 with deck.gl's `ScatterplotLayer` after measurement, or if the lab
  asks for Vitessce specifically.

**Building block:** client-side rendering tier of a static-site architecture (thick client over a CDN-style static origin).
