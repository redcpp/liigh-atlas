# ADR-0008 — Public generic tool vs private study overlay

Status: Proposed (maintainer gate after Phase 0; final shape depends on Q10)

## Context

The code must be open source and linked from the paper (FR-R1), but the study is unpublished: lab data
never enters git or public builds (BRIEF §4.1), and whether even the repo and a dev-data demo may be
public before the paper is open (Q10, Dany). Study-specific material — the study title and abstract,
cluster names and palette, clinical allowlist, figure list, methods text — could reveal unpublished
results even without any data file.

## Options

1. **One private repo until publication**, then flip to public: simplest; nothing is public early, and
   history must be scrubbed of anything study-specific before flipping.
2. **One public repo with study content behind `.gitignore`**: easy to leak by accident; no history of
   the private part.
3. **Public generic tool + private overlay repo**: the public repo is a dataset-agnostic "Xenium TMA
   atlas" tool that builds from config; a private overlay (lab-only repo or directory on the encrypted
   volume) holds the study config and text, merged at build time via `ATLAS_OVERLAY_DIR`.

## Decision

**Prepare for option 3, operate as option 1 until Q10 is answered.** The repo stays private now, but
its structure already enforces the split so that making it public later is a visibility change, not a
cleanup.

| Lives in the public tool | Lives in the private overlay |
|---|---|
| Pipeline, web app, tests, CI, docs, ADRs | `datasets/lab.yaml` (paths under `$LAB_DATA_DIR`, column mapping, `visibility: private`) |
| Dataset configs for `ovarian-10x`, `synthetic-tma`, `scale`, `fixture` | Study title, About/Methods/How-to-cite text for the paper |
| Generic content pages with 10x attribution | Cluster labels and palette (Q12), clinical allowlist (Q4) |
| Fixture data (CC BY, 10x) | `figures.yaml` with paper figure URLs |

Rules enforced by the build:
- Content pages and dataset configs are resolved from `ATLAS_OVERLAY_DIR` first, then the public
  defaults; the overlay path must be outside the repo.
- A public build (`make build`) fails if any included dataset is `visibility: private` or if the overlay
  is set without `ATLAS_BUILD=private`.
- The study name ("acral melanoma") appears in the public repo only in docs describing the collaboration
  (as now), pending Q10; the app UI shows the dataset title from config.

## Consequences

- Slight indirection: content and configs are looked up in two places, covered by unit tests.
- On publication, the lab decides whether the overlay text moves into the public repo (becoming the
  paper's companion site) or stays separate; either is a copy, not a refactor.
- If Q10 allows a public repo early, only the visibility flag changes; no history rewrite is needed
  because study data and text never entered it.

**Building block:** configuration management and multi-tenancy (tenant overlay on a shared codebase) with a data-privacy boundary.
