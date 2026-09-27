# Data Contract — canonical dataset

Version 0.1 (Phase 0). The adapter boundary of BRIEF §4.4:
`source adapter → canonical dataset (validated) → asset builder → static assets → web app`.
Every source (10x dev data, synthetic, scale, fixture, lab) is converted into exactly this shape; nothing
downstream knows where the data came from. Swapping to lab data = one new adapter + one config file.

Conventions: lengths in **µm** (`_um`), images in **pixels** (`_px`); coordinates are section-local with
origin at the top-left of the section's Xenium image, x to the right, y down (Xenium convention).
IDs are strings, stable across releases (URLs cite them, NFR-16). Types are Arrow/pandas dtypes.
Schemas are implemented with pandera (tables) and pydantic (records); a violation fails the pipeline.

## 1. `cells`

One row per segmented cell kept in the dataset.

| Field | Type | Unit | Null | Invariant |
|---|---|---|---|---|
| `cell_id` | string | — | no | unique within the dataset |
| `section_id` | string | — | no | ∈ `sections.section_id` |
| `core_id` | string | — | no | ∈ `cores.core_id`; the core's `section_id` equals the cell's |
| `patient_id` | string | — | no | equals `cores.patient_id` of its core (denormalized for validation) |
| `x_um`, `y_um` | float64 | µm | no | finite; inside the section bounds; within `radius_um` + 50 µm of its core center (TMA) or inside the core `bbox` (whole tissue) |
| `umap_x`, `umap_y` | float32 | — (unitless) | no | finite |
| `cluster_id` | string | — | no | ∈ `clusters.cluster_id` |
| `n_transcripts` | int32 | count | no | ≥ 0; from the source's per-cell total (`transcript_counts` for Xenium); the pipeline compares it with the counts row sum and fails if they disagree for > 0.1% of cells |

Whole-tissue sources (dev data) emit one `core` per section of `kind: region` covering the tissue
bounding box, so every cell has a core and the TMA Map still works.

## 2. `genes`

| Field | Type | Null | Invariant |
|---|---|---|---|
| `gene_id` | string | no | unique (Ensembl ID when available, else the source feature id) |
| `symbol` | string | no | unique case-insensitively within the dataset (duplicates suffixed `-2`, logged) |
| `panel` | category: `predesigned` \| `custom` | no | from `gene_panel.json` (dev: 5,001 predesigned + 100 custom targets; 5,101 gene features in the matrix) |

Only features of type `Gene Expression` are genes; control probes and codewords are dropped and counted
in the report.

## 3. `expression`

Sparse cells × genes matrix, rows in `cells` order, columns in `genes` order.

| Layer | Type | Invariant |
|---|---|---|
| `counts` | CSR int32 | ≥ 0; shape = (`len(cells)`, `len(genes)`) |
| `display` | derived at build time, not stored canonically | `log1p(counts / n_counts_total × 10⁴)`; method, scale factor and version recorded in `dataset.provenance` |

Display values are quantized per gene to `uint8` with `q = round(255 · v / max_v)`; `max_v` is stored
per gene in the manifest so the color bar shows real units (ADR-0003). The normalization is configurable
to match the lab's figures (Q15).

## 4. `clusters`

| Field | Type | Null | Invariant |
|---|---|---|---|
| `cluster_id` | string | no | unique; stable slug |
| `label` | string | no | from source data or config only — never invented; unknown → `Cluster N` |
| `color` | string `#RRGGBB` | no | from config (Q12) or the generated color-blind-safe palette (NFR-7) |
| `order` | int16 | no | unique; display order in the legend |
| `n_cells` | int32 | no | equals the count in `cells` |

Expected count: 23 for `lab` and `scale`; 18 for `ovarian-10x` (17 groups + Unassigned). A config
value `expected_clusters` makes the mismatch a failure.

## 5. `cores`

| Field | Type | Unit | Null | Invariant |
|---|---|---|---|---|
| `core_id` | string | — | no | unique |
| `section_id` | string | — | no | ∈ `sections` |
| `patient_id` | string | — | no | pseudonymous code in public builds (`P01`…); never a hospital or record ID |
| `kind` | category: `core` \| `region` | — | no | `region` only for whole-tissue sources |
| `center_um` | [float64, float64] | µm | no | inside the section bounds |
| `radius_um` | float64 | µm | no | > 0; ~500 for a 1 mm core |
| `bbox` | [x0, y0, x1, y1] float64 | µm | no | contains every cell of the core; cores of one section do not overlap (TMA) |
| `cell_range` | [start, end) int64 | index | no | filled by the asset builder: contiguous range after ordering |
| `clinical` | map<string, string> | — | yes | keys ⊆ the public allowlist in config (Q4); empty by default |

## 6. `sections`

| Field | Type | Unit | Null | Invariant |
|---|---|---|---|---|
| `section_id` | string | — | no | unique |
| `he_image` | string (path relative to the raw root) | — | yes | readable OME-TIFF when present |
| `affine` | 3×3 float64 | µm → H&E px | yes | invertible; required when `he_image` is set; last row `[0, 0, 1]` |
| `affine_source` | 3×3 float64 | as provided (10x: H&E px → Xenium px) | yes | the source alignment matrix, verbatim; `affine` is derived from it; both are written to the manifest (Gate 0) |
| `pixel_size` | float64 | µm / Xenium px | no | dev data: 0.2125 (from `experiment.xenium`) |
| `he_pixel_size_um` | float64 | µm / H&E px | yes | source H&E pixel size derived from `affine_source` (dev: ≈ 0.274); written to the manifest; the pre-aligned pyramid's pixel size is ≤ this |
| `bounds_um` | [x0, y0, x1, y1] | µm | no | contains every cell of the section |

`affine` is stored in the direction the pipeline uses (µm → H&E px). For 10x data it is composed as
`inverse(A_align) · diag(1/pixel_size, 1/pixel_size, 1)`, where `A_align` is the Xenium Explorer
alignment matrix (H&E px → Xenium px). The Phase 1 alignment test verifies this direction empirically.

## 7. `dataset`

| Field | Type | Invariant |
|---|---|---|
| `name` | string | matches the config key (`ovarian-10x`, `synthetic-tma`, `scale`, `fixture`, `lab`) |
| `title` | string | shown in the UI |
| `license` | string (SPDX) | dev: `CC-BY-4.0`; lab: pending (Q9) |
| `citation` | string | text shown by "Copy citation" and on the How-to-cite page |
| `provenance` | record | source URLs, md5s, adapter name + version, normalization, seed, pipeline version; UMAP source (`provided` \| `recomputed`), both kNN coherence scores, parameters and hash of the cached embedding |
| `synthetic` | bool | `true` for `synthetic-tma`, `scale`, `fixture`; drives the "Synthetic data" badge (FR-P5) |
| `visibility` | category: `public` \| `private` | `lab` is `private` until Q5/Q10 say otherwise (NFR-8) |
| `release` | string | content hash prefix of the manifest; URLs pin it (ADR-0005) |

## 8. Validation

Per-table schema checks (types, nulls, ranges, uniqueness) plus cross-entity invariants:
1. Referential integrity: cells → cores → sections; cells → clusters; expression shape = cells × genes.
2. `cells.patient_id` equals its core's `patient_id`; every core has ≥ 1 cell.
3. Spatial containment: cells inside their core (see `cells`), cores inside their section.
4. Counts: `n_transcripts` agrees with the counts row sum (≤ 0.1% of cells may differ); `clusters.n_cells` equals the observed counts.
5. Known totals per dataset from config: `ovarian-10x` must have 407,124 cells and a median of 178
   transcripts per cell (10x metrics); `scale` ≥ 443,000 cells, ≥ 100 cores, 62 patients, 3 sections,
   23 clusters.
6. Privacy: for `visibility: private`, validation reports only aggregate counts; failing rows are
   reported as counts, never values.

## 9. Adapter interface

```python
class SourceAdapter(Protocol):
    name: str                       # dataset config key
    def raw_files(self) -> list[RawFile]:          # every file it will open, with tier and expected size/md5
        ...
    def load(self, cfg: DatasetConfig) -> CanonicalDataset:  # pure; opens only files from raw_files()
        ...

@dataclass(frozen=True)
class CanonicalDataset:
    dataset: DatasetRecord
    sections: pd.DataFrame
    cores: pd.DataFrame
    clusters: pd.DataFrame
    genes: pd.DataFrame
    cells: pd.DataFrame
    expression: scipy.sparse.csr_matrix   # counts, int32
```

Adapters planned: `ovarian-10x` (outs/ + supplemental CSVs), `synthetic-tma` and `scale` (derived from
the `ovarian-10x` canonical dataset, seeded), `fixture` (subset of `synthetic-tma`), `lab` (Xenium
`outs/` per section + annotation table `cell_id, section, cluster_label, umap_1, umap_2` + TMA map +
H&E alignment; Phase 4). Lab-specific unknowns (column names, file formats) live in the lab dataset
config, not in code.

**Source mapping for `ovarian-10x`:** `cells.parquet` (`cell_id`, `x_centroid`, `y_centroid`,
`transcript_counts`) · `cell_feature_matrix.h5` (counts, features) · Cell Groups CSV (`cell_id`,
`group`, `color`) → clusters · UMAP: `analysis/umap/gene_expression_2_components/projection.csv` (`Barcode`,
`UMAP-1`, `UMAP-2`) or the seeded scanpy recompute cached in `$DATA_ROOT/derived/`, whichever scores
higher on kNN cluster coherence (TECH_SPEC §2) · H&E Image Alignment CSV → `affine` · `experiment.xenium` → `pixel_size`.
