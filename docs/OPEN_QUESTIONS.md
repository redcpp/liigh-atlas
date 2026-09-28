# Open Questions

Seeded from BRIEF §11 (Q1–Q12) plus questions raised in Phase 0 (Q13–Q16). Each open question has a
default assumption so work continues behind configuration (BRIEF §0); defaults are `[Assumption]` until
answered. Recipients: **Estef** (Estefanía Vázquez-Cruz, data and science, daily contact), **Dany**
(Dra. Daniela Robles-Espinoza, director: scope, paper, publication only), **Jair** (Jair García,
infrastructure). **Nothing is sent now** (Gate 0, `[Diego]`): the strategy is demo-first (BRIEF §1), so
the lab's questions are held for the in-person meeting after the Phase 3 demo (agenda below) and Jair's
for the deployment step (Phase 6). Answers are recorded here and in the PRD changelog when they change a
requirement.

| ID | Question | Recipient | Blocks | Status | Default assumption (used meanwhile) |
|---|---|---|---|---|---|
| Q1 | Format, location and columns of the processed object; at minimum the annotation CSV (`cell_id, section, cluster_label, umap_1, umap_2`) | Estef | Phase 4 (lab adapter) | Pending — meeting | The lab exports the annotation CSV from Seurat/scanpy; column names are mapped in `datasets/lab.yaml` |
| Q2 | One complete Xenium `outs/` per section (selective copy, BRIEF §4.1) | Estef | Phase 4 | Pending — meeting | Standard Xenium Onboard Analysis `outs/` with the files of the handoff list |
| Q3 | Is the H&E aligned to Xenium? Format and resolution | Estef | Phase 4 (FR-C1, FR-C5 on lab data) | Pending — meeting | A Xenium Explorer alignment CSV exists per section; otherwise landmark registration in Phase 4 |
| Q4 | Core ↔ sample ↔ patient table; which clinical metadata may be public | Estef | Phase 4 (cores, FR-C4, FR-T3) | Pending — meeting | TMA map provided as CSV; public builds show pseudonymous patient codes and no clinical fields |
| Q5 | Will all ~443K cells and ~5K genes be published? | Estef / Dany | Public lab build (Phase 4 itself runs privately meanwhile) | Pending — meeting | All cells and genes, lab dataset `visibility: private` until confirmed |
| Q6 | Journal; site inside the atlas paper or a separate note; raw-data deposit | Dany | Deadline, How-to-cite page | Partial: submission ~March 2027 `[Diego]`; rest open | Site cited from the atlas paper; raw data deposited by the lab separately |
| Q7 | Priority among the three views | Estef | Phase order | Pending | UMAP first (cheapest, de-risks rendering at scale), then TMA Map + Core Detail |
| Q8 | Public web server, domain, HTTPS, quota | Jair | Deployment | Answered `[Diego]` → NFR-2 (confirm with Jair before deploy) | nginx on a LIIGH server, `atlas.liigh.unam.mx`, Let's Encrypt, ≥ 10 GB |
| Q9 | Repo owner and license | Dany | Release | Answered `[Diego]`: repo under `redcpp`, lab as collaborator; license MIT still `[Assumption]` | MIT license |
| Q10 | May the repo and a demo with public 10x data be public before the paper? | Dany | Public repo/demo | Open | Repo private; public/private split prepared (ADR-0008) |
| Q11 | Do reviewers need access to the site with real data? | Dany | Phase 4 timing | Answered `[Diego]`: no; screenshots + code (FR-G7, FR-P8) | No reviewer deployment |
| Q12 | Names and palette of the 23 clusters as used in the paper figures | Estef | FR-G5, NFR-7 | Pending — meeting | Labels from the annotation table; generated color-blind-safe palette |
| Q13 | Server details: file-count or inode limits (~5K per-gene files + tile pyramids per release; measured dev build `ovarian-10x`: 11,767 files, 402.3 MB; projected lab TMA build: ≈ 13,800 files and ≈ 0.5 GB per release at 100 cores, ≈ 18,200 files at 150 cores `[Assumption]`), brotli module, deploy access (SSH/rsync), retention of the previous release | Jair | Phase 6 deploy (ADR-0003, ADR-0006) | Open (new) | No file-count limit; gzip only; rsync over SSH; keep one previous release |
| Q14 | Is the UMAP one integrated embedding across all sections (batch-corrected) or one per section? | Estef | Phase 4 (FR-U1 on lab data) | Open (new) | One integrated UMAP in the annotation table |
| Q15 | Normalization used for expression in the paper figures (Seurat LogNormalize, SCTransform, other) | Estef | Phase 4 (FR-G3 parity with figures) | Open (new) | `log1p(counts / total × 10⁴)` (Seurat LogNormalize default), configurable |
| Q16 | Authors and citation text for the site before the paper exists | Dany | FR-P1, FR-P4 content | Open (new) | Cite the software (repo, later Zenodo DOI) with "manuscript in preparation" |

## Meeting agenda

In-person meeting after the Phase 3 demo, with the drive and the handoff list (BRIEF §4.1). Ordered by
what each answer unblocks, Phase 4 first. Estef answers unless marked; Dany's items are grouped so her
time is used only for scope and publication decisions.

### 1. Unblocks Phase 4 — lab data handoff (Estef)
1. **Q2** Copy one Xenium `outs/` per section, only the handoff-list files (selective, ≤ 2 GB/section).
   Handoff checklist addition (Gate 1, `[Diego]`): `cells.zarr.zip`, one per section, **test-only** input for
   the spatialdata-io oracle (T-PIPE-ORACLE-01) that must pass before the lab's Xenium version is allowed;
   the pipeline never reads it. Estimate ~460 MB total, scaled from 425 MB for 407,124 dev cells to
   ~443K cells `[Assumption]`.
2. **Q1** Annotation table `cell_id, section, cluster_label, umap_1, umap_2`: format and source (Seurat or scanpy).
3. **Q4** TMA map core ↔ sample ↔ patient; which clinical fields may be public.
4. **Q3** Is the H&E aligned to Xenium? Alignment file, format, resolution.
5. **Q14** One integrated UMAP across all sections, or one per section?
6. **Q15** Normalization used for the expression figures.
7. **Q12** Names and palette of the 23 clusters as in the paper figures.

### 2. Unblocks what may be public (Dany; Q5 with Estef)
8. **Q5** Will all ~443K cells and ~5K genes be published?
9. **Q10** May the repo and a dev-data demo be public before the paper?

### 3. Unblocks citation and release content (Dany)
10. **Q6** Journal; site cited inside the atlas paper or a separate note; raw-data deposit.
11. **Q16** How to cite the site before the paper exists.
12. **Q9** Confirm the MIT license (repo owner already answered).

### 4. Informs Phase 5 priorities (Estef)
13. **Q7** Which view matters most to the lab, after seeing the demo.

## Deployment step — Jair

Held until Phase 6, sent with `docs/DEPLOY.md`.
1. **Q8** Confirm server, subdomain `atlas.liigh.unam.mx` and quota ≥ 10 GB.
2. **Q13** File-count or inode limits (~5K per-gene files + H&E tiles per release; dev build measured at
   11,767 files / 402.3 MB, lab TMA projected at ≈ 13,800 files / ≈ 0.5 GB per release, see the note below); brotli module or gzip
   only; upload access (SSH/rsync); how many previous releases to keep.

## Q13 projection (for Jair, Phase 6)

Measured `[Diego]` (Phase 1, `ovarian-10x` release `681e291a3964`; after the Gate 1 changes `77b97a69f5a1`: 11,767 files, 402.35 MB): 11,767 files, 402.3 MB —
5,101 per-gene expression files (161.4 MB), 6,652 H&E tiles (233.8 MB), 14 other files.

Projected lab TMA release `[Assumption]` (inputs: ~5,000 genes, 100+ cores of 1 mm, H&E at 0.270 µm/px,
512 px tiles, 35 KB per tile as measured): each core crop is 1,100 µm → 4,075 px → 4 levels of
64 + 16 + 4 + 1 = 85 tiles, plus `pyramid.json` and a thumbnail = 87 files per core.

| Cores | Expression | H&E files | Other | Total files | Size |
|---|---|---|---|---|---|
| 100 | ~5,100 | 8,700 | ~15 | ≈ 13,800 | ≈ 0.5 GB |
| 150 | ~5,100 | 13,050 | ~15 | ≈ 18,200 | ≈ 0.65 GB |

Two releases kept on disk (current + previous, ADR-0006) double these numbers.

