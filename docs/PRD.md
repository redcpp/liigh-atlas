# PRD — Acral Melanoma Spatial Atlas

Version 0.1 (Phase 0). Derived from `docs/BRIEF.md`, which stays read-only; every change after this
version is recorded in the [changelog](#changelog). Source tags follow BRIEF §0:
`[PDF]` lab's written brief · `[Call]` kickoff meeting · `[Assumption]` inferred, not validated ·
`[Product]` maintainer's product-quality decision · `[Diego]` maintainer's answer on the lab's behalf.
An `[Assumption]` is never promoted to fact here: it keeps its tag until the lab validates it and the
changelog records the change.

## 1. Problem

The LIIGH-UNAM acral melanoma Xenium study (62 patients, 100+ TMA cores, ~443K cells, ~5K genes,
23 annotated clusters) is explored today with Xenium Explorer (commercial desktop app) and loose Plotly
HTML files `[Call]`. Nothing is shareable, linkable or citable. When the paper is submitted (~March 2027)
reviewers and readers have no way to verify a figure or ask "where is gene X expressed in these
patients?" without installing software and obtaining ~300 GB of raw data.

## 2. Goals and non-goals

**Goals**
1. A public, open-source, static website that lets anyone find a gene and see where it is expressed, on
   the UMAP and on the tissue, in under a minute (US-1, US-5).
2. Link the two spaces of every cell — physical (tissue) and similarity (UMAP) — in both directions.
3. Every view is a URL that can be cited in a figure legend and keeps resolving after future releases
   (FR-G6, NFR-16).
4. The lab can regenerate the whole site from raw data with one command and produce publication figures
   from view URLs (FR-R2, FR-P8).
5. Production quality measured by thresholds (§8), not by feature count.

**Non-goals (v1, BRIEF §7)** — each with the cost that rules it out:
individual transcripts (billions of points; breaks NFR-3/NFR-5) · 3D tissue reconstruction (sections are
~5 µm, effectively 2D) · user-run analysis such as differential expression or re-clustering (breaks
NFR-1) · accounts and user uploads · the HPC cluster as web server · Plotein 2.0 deployment.

## 3. Personas

| Persona | Needs | Typical entry |
|---|---|---|
| External researcher | Find a gene, see which cell types and which tissue regions express it | Search engine or paper link → UMAP Atlas |
| Paper reviewer | Open the exact view behind a figure panel and check it is what the legend says | Figure-legend URL → any view |
| Lab member | Compare cores and patients, produce figures reproducibly | TMA Map → Core Detail, `make figures` |

## 4. User stories

| ID | Story | P | Source |
|---|---|---|---|
| US-1 | Type a gene and see its expression on the UMAP and on the tissues | M | `[PDF][Call]` |
| US-2 | Pick a core and see its H&E next to its annotated cells | M | `[PDF]` |
| US-3 | Put several cores side by side to compare patients | M | `[PDF]` |
| US-4 | Open the site from a link at an exact view, citable in a figure | M | `[PDF]` |
| US-5 | A first-time visitor understands what the atlas is and how to use it in < 60 s | M | `[Product]` |

## 5. Functional requirements

MoSCoW: M must · S should · C could (only via ADR) · W won't (v1). Priorities and tags as in BRIEF §5.

### 5.1 Global

| ID | Requirement | P | Source |
|---|---|---|---|
| FR-G1 | One app, three views: UMAP Atlas, TMA Map, Core Detail | M | `[PDF][Assumption]` |
| FR-G2 | Linked selection across views (cells, cluster, core, patient) | M | `[Assumption]` |
| FR-G3 | Color by cluster, patient, core or gene expression | M | `[Assumption]` |
| FR-G4 | Gene search with autocomplete (symbol, case-insensitive) | M | `[Assumption]` |
| FR-G5 | Legend of the 23 clusters: toggle, isolate, hover highlight | M | `[PDF]` |
| FR-G6 | Full view state in the URL; shareable and citable | M | `[PDF]` |
| FR-G7 | Export current view as PNG (publication resolution) and SVG (legend/axes) | M | `[Diego]` |

### 5.2 UMAP Atlas

| ID | Requirement | P | Source |
|---|---|---|---|
| FR-U1 | All ~443K cells rendered, no subsampling | M | `[PDF]` |
| FR-U2 | Hover shows cluster, patient, core (and gene value when coloring by gene) | M | `[Assumption]` |
| FR-U3 | Filter / isolate clusters | M | `[Assumption]` |
| FR-U4 | Lasso selection | S | `[Assumption]` |
| FR-U5 | 3D UMAP | C | `[PDF]` |

### 5.3 TMA Map

| ID | Requirement | P | Source |
|---|---|---|---|
| FR-T1 | Each section with its cores at real positions | M | `[PDF]` |
| FR-T2 | Click a core → opens its Core Detail | M | `[Call]` |
| FR-T3 | Hover a core → H&E thumbnail + patient | S | `[PDF]` |
| FR-T4 | Embed the lab's current Plotly HTML as a provisional view (only if the lab provides the file) | C | `[PDF]` |

### 5.4 Core Detail

| ID | Requirement | P | Source |
|---|---|---|---|
| FR-C1 | H&E and spatial cell plot side by side, synchronized pan/zoom | M | `[PDF]` |
| FR-C2 | Zoom down to single-cell level | M | `[Call]` |
| FR-C3 | Compare several cores side by side | M | `[PDF]` |
| FR-C4 | Group all cores of one patient | M | `[PDF]` |
| FR-C5 | Cells overlaid on the H&E with adjustable opacity | S | `[Assumption]` |
| FR-C6 | Cell outlines when zoomed in | C | `[Assumption]` |

### 5.5 Integration

| ID | Requirement | P | Source |
|---|---|---|---|
| FR-R1 | Open-source code linked from the paper | M | `[PDF][Call]` |
| FR-R2 | Pipeline regenerates every asset from raw data with one command | M | `[Assumption]` |

### 5.6 Polish

| ID | Requirement | P | Source |
|---|---|---|---|
| FR-P1 | Pages: About the atlas, Methods, How to cite, License & data provenance (incl. 10x CC BY) | M | `[Product]` |
| FR-P2 | First-visit hints (dismissible) + keyboard-shortcuts panel | M | `[Product]` |
| FR-P3 | Complete UI states: progressive loading with progress, empty, error with retry, WebGL-unsupported fallback | M | `[Product]` |
| FR-P4 | "Copy link" and "Copy citation" for the current view | M | `[Product]` |
| FR-P5 | Dataset selection driven by build config; synthetic data visibly labeled | M | `[Product]` |
| FR-P6 | Light/dark theme following the OS | S | `[Product]` |
| FR-P7 | QC page linking each section's `analysis_summary.html` | C | `[Call]` |
| FR-P8 | Scripted figure pack: `make figures` renders the view URLs in `docs/figures.yaml` to publication PNG/SVG, reproducibly | M | `[Diego]` |

## 6. Non-functional requirements

BRIEF §6 gives NFRs no MoSCoW column; all are **M** because their thresholds are acceptance criteria.
Measurement method for each lives in `docs/TECH_SPEC.md` §7 and `docs/adr/0007-testing-and-performance.md`.

| ID | Requirement | Threshold / how measured | P | Source |
|---|---|---|---|---|
| NFR-1 | No runtime compute | Server serves static files only | M | `[Call]` |
| NFR-2 | Hosting | nginx on a public LIIGH server, subdomain like `atlas.liigh.unam.mx`, HTTPS (Let's Encrypt), quota ≥ 10 GB; public demo host with dev data; range requests, compression, long cache for hashed assets | M | `[Call][Diego]` |
| NFR-3 | Initial load | < 5 MB transferred before first interaction (Playwright network log) | M | `[Assumption]` |
| NFR-4 | Gene switch | p95 < 300 ms over 50 random genes, cold per-gene cache, local static server | M | `[Assumption]` |
| NFR-5 | Rendering | Median ≥ 55 fps during scripted pan/zoom with all cells, reference laptop in `docs/perf.md` | M | `[Assumption]` |
| NFR-6 | Browsers | Latest desktop Chrome, Firefox, Safari; mobile best-effort, read-only | M | `[Assumption]` |
| NFR-7 | Color | Color-blind-safe palettes; 23-color palette checked under protan/deutan; never color-only encoding | M | `[Assumption]` |
| NFR-8 | Privacy | Only de-identified data in public builds; lab previews private (plus hard rule BRIEF §4.1) | M | `[Assumption]` |
| NFR-9 | Citability | Code citable with a DOI (Zenodo) at release | M | `[Assumption]` |
| NFR-10 | Accessibility | WCAG 2.1 AA for UI chrome; axe-core 0 serious/critical; all controls keyboard-operable | M | `[Product]` |
| NFR-11 | Lighthouse (desktop, main view) | Performance ≥ 85, Accessibility ≥ 95, Best Practices ≥ 95 | M | `[Product]` |
| NFR-12 | Hygiene | Zero console errors during the e2e suite | M | `[Product]` |
| NFR-13 | Asset size | ≤ ~5 GB total at lab scale; size reported per asset family | M | `[Product]` |
| NFR-14 | Reproducibility | Same input → byte-identical assets (hash manifest); one command | M | `[Product]` |
| NFR-15 | Tests | Pipeline ≥ 85% line coverage; web state/data modules ≥ 80%; every M/S ID covered by ≥ 1 e2e test | M | `[Product]` |
| NFR-16 | Stable citations | URLs cited in the paper keep resolving after future releases (versioned URL schema + fixtures) | M | `[Product]` |

## 7. Acceptance criteria

One or more Given/When/Then per Must/Should. "Dataset" means any build-configured dataset; performance
criteria are judged on `scale` (≥ 443K cells) unless stated. Test IDs are in `docs/TEST_PLAN.md`.

### User stories
- **AC-US-1.1** Given the UMAP Atlas is loaded, when the visitor types "epc" and picks `EPCAM` from the suggestions, then every cell on the UMAP and on every visible tissue is colored by `EPCAM` expression with a labeled continuous color bar.
- **AC-US-1.2** Given a gene is selected, when the visitor opens the TMA Map or a Core Detail, then the same gene coloring is kept without re-selecting it.
- **AC-US-2.1** Given the TMA Map, when the visitor clicks a core, then Core Detail shows that core's H&E and its cells colored by cluster side by side within the core-open budget (TECH_SPEC §7).
- **AC-US-3.1** Given Core Detail of one core, when the visitor adds three more cores from other patients, then four panels appear side by side, each labeled with core and patient, sharing color mode and legend.
- **AC-US-4.1** Given any view reached by interaction, when its URL is copied and opened in a fresh browser profile, then the same view (dataset release, view, color mode, gene, filters, selection, camera) is restored.
- **AC-US-5.1** Given a first-time visitor on the landing view, when they follow the first-visit hints, then within 60 s they can state what the atlas shows and have colored the UMAP by a gene (moderated test with ≥ 3 people outside the lab, median ≤ 60 s).

### Global
- **AC-FR-G1.1** Given the app is loaded, when the visitor uses the view switcher, then UMAP Atlas, TMA Map and Core Detail are reachable in one click each inside one single-page app, with no full page reload.
- **AC-FR-G2.1** Given cells are selected (lasso, cluster, core or patient) in one view, when the visitor switches or looks at another linked view, then exactly the same cells are highlighted there and the rest are dimmed.
- **AC-FR-G2.2** Given a core is hovered in the TMA Map, when the UMAP is visible, then that core's cells are highlighted on the UMAP within 100 ms.
- **AC-FR-G3.1** Given any view, when the visitor picks color by cluster, patient, core or gene, then points are recolored accordingly and the legend or color bar matches the mode.
- **AC-FR-G4.1** Given the search box, when the visitor types a case-variant prefix ("cd8", "CD8"), then the suggestions list matching symbols ranked exact-prefix first, keyboard-navigable, within 50 ms.
- **AC-FR-G4.2** Given the visitor types a symbol not in the panel, when they press Enter, then an empty state says the gene is not in the panel and suggests the closest symbols.
- **AC-FR-G5.1** Given the cluster legend with 23 entries, when the visitor clicks an entry, then that cluster toggles visibility; when they alt-click (or use the isolate button), then only that cluster remains visible; when they hover it, then its cells are highlighted in every view.
- **AC-FR-G6.1** Given any view state, when it is serialized to the URL and the URL is reloaded, then the deserialized state is identical (round-trip over 20 random states) and the URL is at most 2,000 characters.
- **AC-FR-G7.1** Given any view, when the visitor exports PNG, then a raster of at least 300 dpi at 180 mm width (≥ 2,126 px) with the same content as the screen is downloaded; when they export SVG, then legend, axes and scale bar are vector.

### UMAP Atlas
- **AC-FR-U1.1** Given the `scale` dataset, when the UMAP Atlas finishes loading, then the number of drawn points equals the dataset cell count (no subsampling), verified from the render layer's instance count.
- **AC-FR-U2.1** Given the pointer is over a cell, when the hover card appears, then it shows cluster label, patient and core, and the gene value when coloring by gene, within 50 ms.
- **AC-FR-U3.1** Given the cluster filter, when the visitor hides or isolates clusters, then only cells of the visible clusters are drawn and pickable, and the filter is reflected in the URL.
- **AC-FR-U4.1** Given the lasso tool, when the visitor draws a polygon on the UMAP, then the enclosed cells become the selection (count shown) within 200 ms, and the selection is linked to the other views (FR-G2).

### TMA Map
- **AC-FR-T1.1** Given a dataset with sections and cores, when the TMA Map opens, then each section is drawn with its cores at their real `center_um` and `radius_um`, labeled by core ID, and the positions match the canonical `cores` table within 1 µm.
- **AC-FR-T2.1** Given the TMA Map, when the visitor clicks or presses Enter on a focused core, then Core Detail of that core opens and the URL changes to it.
- **AC-FR-T3.1** Given the TMA Map, when the visitor hovers or focuses a core, then a card with its H&E thumbnail and patient ID appears within 150 ms.

### Core Detail
- **AC-FR-C1.1** Given Core Detail, when the visitor pans or zooms either the H&E panel or the cell panel, then the other panel follows to the same µm viewport (error < 1 screen pixel).
- **AC-FR-C2.1** Given Core Detail, when the visitor zooms in, then zoom reaches at least 0.25 µm per screen pixel with the H&E at full resolution, so single nuclei and individual cell points are distinguishable.
- **AC-FR-C3.1** Given one open core, when the visitor adds cores (up to at least 6) to the comparison, then they render side by side with shared color mode and legend, and the comparison is encoded in the URL.
- **AC-FR-C4.1** Given a patient with ≥ 2 cores, when the visitor chooses "all cores of this patient", then all and only that patient's cores open in the comparison grid.
- **AC-FR-C5.1** Given Core Detail, when the visitor moves the overlay opacity slider from 0 to 100%, then cells are drawn on top of the H&E at that opacity and the value persists in the URL.

### Integration
- **AC-FR-R1.1** Given the release, when a reader follows the repository link from the site footer or the paper, then the source code with README, LICENSE and CITATION.cff is available and builds with the documented commands.
- **AC-FR-R2.1** Given raw data in `$DATA_ROOT` (or `$LAB_DATA_DIR`), when the maintainer runs `make pipeline DATASET=<name>`, then every static asset of that dataset is regenerated with no manual step.

### Polish
- **AC-FR-P1.1** Given the site, when the visitor opens About, Methods, How to cite or License & data provenance, then each page exists, is reachable from the header and footer, and the provenance page credits 10x Genomics under CC BY 4.0 for the development dataset.
- **AC-FR-P2.1** Given a first visit, when the app loads, then dismissible hints point at search, legend and view switcher; when dismissed they do not reappear; when the visitor presses `?`, then a keyboard-shortcuts panel opens.
- **AC-FR-P3.1** Given assets are loading, when the visitor waits, then a progress indicator shows bytes loaded; given an asset request fails, when the error state shows, then "Retry" reloads only the failed asset; given WebGL is unavailable, then a fallback page explains the requirement.
- **AC-FR-P3.2** Given a filter that leaves no visible cells, when the view renders, then an empty state explains why and offers "Reset filters".
- **AC-FR-P4.1** Given any view, when the visitor clicks "Copy link" or "Copy citation", then the clipboard holds the versioned URL or a citation text (dataset, release, view URL) and a confirmation is announced to screen readers.
- **AC-FR-P5.1** Given a build config naming datasets, when the app starts, then only those datasets are selectable, and any dataset with `synthetic: true` shows a persistent "Synthetic data" badge in every view and in exports.
- **AC-FR-P6.1** Given the OS color scheme is dark (or light), when the app loads, then the UI chrome uses the matching theme and all text meets WCAG AA contrast in both.
- **AC-FR-P8.1** Given `docs/figures.yaml` listing view URLs and export settings, when the maintainer runs `make figures` twice, then the same PNG/SVG files with identical hashes are produced.

### Non-functional
- **AC-NFR-1.1** Given the built site, when it is served by a plain static server with no application runtime, then every e2e test passes.
- **AC-NFR-2.1** Given the nginx config in `docs/DEPLOY.md`, when a hashed asset is requested, then the response has `Cache-Control: immutable`, compression when requested, HTTP 206 for a range request, and HTTPS in production.
- **AC-NFR-3.1** Given a cold cache, when the main view becomes interactive, then the Playwright network log sums < 5 MB transferred.
- **AC-NFR-4.1** Given a cold per-gene cache and a local static server, when the bench switches among 50 random genes, then p95 from selection to painted frame is < 300 ms.
- **AC-NFR-5.1** Given all cells rendered on the reference laptop, when the scripted pan/zoom runs, then median fps ≥ 55.
- **AC-NFR-6.1** Given the e2e suite, when it runs on Playwright chromium, firefox and webkit, then it passes on all three; given a mobile viewport, when the site opens, then it is readable and navigable read-only.
- **AC-NFR-7.1** Given the 23-color palette, when simulated under protanopia and deuteranopia, then every pair of colors has ΔE2000 ≥ 10 (or, when that is impossible, clusters are also distinguishable by label and hover highlight, never by color alone).
- **AC-NFR-8.1** Given a public build, when the build guard inspects its config and manifest, then it fails if any dataset is marked `visibility: private`, and patient IDs are pseudonymous codes only.
- **AC-NFR-9.1** Given a release, when it is archived on Zenodo, then the README and CITATION.cff carry the DOI.
- **AC-NFR-10.1** Given every view, when axe-core runs, then there are 0 serious/critical violations; when using only the keyboard, then every control is reachable and operable with a visible focus.
- **AC-NFR-11.1** Given the main view in desktop mode, when Lighthouse runs, then Performance ≥ 85, Accessibility ≥ 95, Best Practices ≥ 95.
- **AC-NFR-12.1** Given the e2e suite, when it runs, then no test records a console error.
- **AC-NFR-13.1** Given the lab-scale (`scale`) build, when the pipeline finishes, then total assets ≤ 5 GB and a size report per asset family is printed.
- **AC-NFR-14.1** Given the same raw input, when the pipeline runs twice, then the hash manifests are byte-identical.
- **AC-NFR-15.1** Given `make verify`, when coverage is reported, then pipeline ≥ 85% lines, web state/data ≥ 80%, and the traceability check finds an e2e test for every M/S ID.
- **AC-NFR-16.1** Given committed v1 URL fixtures, when a later release is built, then every fixture still resolves to its recorded state and dataset release.

## 8. Definition of polish

"Polished" means all of the following are true, measured, and recorded in `docs/perf.md` — never judged by eye:
1. Every M and S acceptance criterion above passes on chromium, firefox and webkit.
2. Budgets: NFR-3, NFR-4, NFR-5 and the per-interaction budgets in TECH_SPEC §7.
3. NFR-10 (axe 0 serious/critical, keyboard-only walkthrough), NFR-11 (Lighthouse), NFR-12 (0 console errors).
4. Every UI state exists: loading with progress, empty, error with retry, WebGL fallback (FR-P3).
5. Content pages, attribution, citation and copy-link work (FR-P1, FR-P4); synthetic data is always labeled (FR-P5).
6. Reproducible: one-command pipeline and figures, byte-identical hashes (NFR-14, FR-P8).

## 9. Success metrics

| Metric | Target | How |
|---|---|---|
| Time to first gene view (new visitor) | median ≤ 60 s | US-5 moderated test, ≥ 3 people outside the lab |
| Paper figure panels with a working atlas URL | 100% of atlas-derived panels | `docs/figures.yaml` + NFR-16 fixtures |
| Lab can rebuild without the maintainer | one documented command | fresh-clone test (Phase 6) |
| Budget compliance | 100% of NFR thresholds met | `docs/perf.md` |
| Lab approval | yes | human gate, outside the agent |

## 10. Risks

| ID | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Lab data format unknown (Q1) | Phase 4 slips | Canonical contract + adapter; handoff list BRIEF §4.1 |
| R2 | H&E not aligned or alignment direction wrong (Q3) | FR-C1/FR-C5 wrong overlay | Empirical alignment test (hematoxylin at centroids); documented registration fallback |
| R3 | Initial payload over 5 MB at 443K cells | NFR-3 fails | Quantized UMAP coordinates (ADR-0002), deferred non-critical arrays |
| R4 | Publication not allowed before the paper (Q10) | No public demo | Repo private until decided; public/private split (ADR-0008) |
| R5 | LIIGH host limits (file count, modules) (Q13) | Deploy blocked | Per-gene files with packed-shard fallback (ADR-0003); DEPLOY.md for Jair |
| R6 | Deadline ~March 2027 with volunteer time | Scope cut | MoSCoW; Could items only via ADR; phases close on exit criteria |
| R7 | Cluster names/palette differ from paper figures (Q12) | Visual mismatch with paper | Palette and labels from config; generated color-blind-safe default |
| R8 | External USB disk is slow | Long pipeline and bench runs | Warm-up pass; disk type recorded in `docs/perf.md` |

## Changelog

| Version | Change | Source |
|---|---|---|
| 0.1 | Initial PRD from BRIEF. US and NFR items given priority M (BRIEF assigns none). Tags and FR priorities copied unchanged. | `[Product]` |
