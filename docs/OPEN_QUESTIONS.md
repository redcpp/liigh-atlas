# Open Questions

Seeded from BRIEF §11 (Q1–Q12) plus questions raised in Phase 0 (Q13–Q16). Each open question has a
default assumption so work continues behind configuration (BRIEF §0); defaults are `[Assumption]` until
answered. Recipients: **Estef** (Estefanía Vázquez-Cruz, data and science, daily contact), **Dany**
(Dra. Daniela Robles-Espinoza, director: scope, paper, publication only), **Jair** (Jair García,
infrastructure). Questions are sent in one batched message per recipient (below), never one by one.
Answers are recorded here and in the PRD changelog when they change a requirement.

| ID | Question | Recipient | Blocks | Status | Default assumption (used meanwhile) |
|---|---|---|---|---|---|
| Q1 | Format, location and columns of the processed object; at minimum the annotation CSV (`cell_id, section, cluster_label, umap_1, umap_2`) | Estef | Phase 4 (lab adapter) | Pending — meeting | The lab exports the annotation CSV from Seurat/scanpy; column names are mapped in `datasets/lab.yaml` |
| Q2 | One complete Xenium `outs/` per section (selective copy, BRIEF §4.1) | Estef | Phase 4 | Pending — meeting | Standard Xenium Onboard Analysis `outs/` with the files of the handoff list |
| Q3 | Is the H&E aligned to Xenium? Format and resolution | Estef | Phase 4 (FR-C1, FR-C5 on lab data) | Pending — meeting | A Xenium Explorer alignment CSV exists per section; otherwise landmark registration in Phase 4 |
| Q4 | Core ↔ sample ↔ patient table; which clinical metadata may be public | Estef | Phase 4 (cores, FR-C4, FR-T3) | Pending — meeting | TMA map provided as CSV; public builds show pseudonymous patient codes and no clinical fields |
| Q5 | Will all ~443K cells and ~5K genes be published? | Estef / Dany | Phase 4, public release | Pending — meeting | All cells and genes, lab dataset `visibility: private` until confirmed |
| Q6 | Journal; site inside the atlas paper or a separate note; raw-data deposit | Dany | Deadline, How-to-cite page | Partial: submission ~March 2027 `[Diego]`; rest open | Site cited from the atlas paper; raw data deposited by the lab separately |
| Q7 | Priority among the three views | Estef | Phase order | Pending | UMAP first (cheapest, de-risks rendering at scale), then TMA Map + Core Detail |
| Q8 | Public web server, domain, HTTPS, quota | Jair | Deployment | Answered `[Diego]` → NFR-2 (confirm with Jair before deploy) | nginx on a LIIGH server, `atlas.liigh.unam.mx`, Let's Encrypt, ≥ 10 GB |
| Q9 | Repo owner and license | Dany | Release | Answered `[Diego]`: repo under `redcpp`, lab as collaborator; license MIT still `[Assumption]` | MIT license |
| Q10 | May the repo and a demo with public 10x data be public before the paper? | Dany | Public repo/demo | Open | Repo private; public/private split prepared (ADR-0008) |
| Q11 | Do reviewers need access to the site with real data? | Dany | Phase 4 timing | Answered `[Diego]`: no; screenshots + code (FR-G7, FR-P8) | No reviewer deployment |
| Q12 | Names and palette of the 23 clusters as used in the paper figures | Estef | FR-G5, NFR-7 | Pending — meeting | Labels from the annotation table; generated color-blind-safe palette |
| Q13 | Server details: file-count or inode limits (~5K per-gene files + tile pyramids per release), brotli module, deploy access (SSH/rsync), retention of the previous release | Jair | Phase 6 deploy (ADR-0003, ADR-0006) | Open (new) | No file-count limit; gzip only; rsync over SSH; keep one previous release |
| Q14 | Is the UMAP one integrated embedding across all sections (batch-corrected) or one per section? | Estef | Phase 4 (FR-U1 on lab data) | Open (new) | One integrated UMAP in the annotation table |
| Q15 | Normalization used for expression in the paper figures (Seurat LogNormalize, SCTransform, other) | Estef | Phase 4 (FR-G3 parity with figures) | Open (new) | `log1p(counts / total × 10⁴)` (Seurat LogNormalize default), configurable |
| Q16 | Authors and citation text for the site before the paper exists | Dany | FR-P1, FR-P4 content | Open (new) | Cite the software (repo, later Zenodo DOI) with "manuscript in preparation" |

## Batched message — Estef

> Hola Estef, para cuando nos veamos con los datos del atlas, estas son mis preguntas (todas tienen un
> supuesto por defecto, así que nada me bloquea hoy):
> 1. (Q1) ¿Me pasas la tabla de anotación `cell_id, sección, cluster, umap_1, umap_2`? ¿Sale de Seurat o scanpy?
> 2. (Q2) ¿Puedo copiar de cada sección solo estos archivos de `outs/`? Te llevo la lista y el disco.
> 3. (Q3) ¿El H&E ya está alineado en Xenium Explorer? ¿Hay CSV de alineación?
> 4. (Q4) ¿Tienes la tabla core ↔ muestra ↔ paciente? ¿Qué datos clínicos pueden ser públicos?
> 5. (Q5) ¿Se publicarán todas las células y genes?
> 6. (Q7) ¿Qué vista te importa más: UMAP, mapa del TMA o detalle del core?
> 7. (Q12) ¿Nombres y colores de los 23 clusters como en las figuras?
> 8. (Q14) ¿El UMAP es uno integrado para todas las secciones?
> 9. (Q15) ¿Qué normalización usaron para las figuras de expresión?

## Batched message — Dany

> Hola Dany, cuatro decisiones de alcance y publicación del atlas, cuando tengas un momento:
> 1. (Q10) ¿Puede ser público el repo, con un demo usando datos públicos de 10x, antes del paper? Mientras, queda privado.
> 2. (Q6) ¿A qué revista va y el sitio se cita dentro del paper del atlas? ¿Dónde se depositan los datos crudos?
> 3. (Q5) ¿Se publicarán todas las células (~443K) y genes (~5K)?
> 4. (Q16) ¿Cómo quieres que se cite el sitio antes de que exista el paper?
> 5. (Q9) Confirmación: ¿licencia MIT para el código?

## Batched message — Jair

> Hola Jair, para preparar el despliegue del atlas en `atlas.liigh.unam.mx` (nginx estático, HTTPS con
> Let's Encrypt, cuota ≥ 10 GB, como `vcfplotein`):
> 1. (Q8) ¿Confirmas servidor, subdominio y cuota?
> 2. (Q13) ¿Hay límite de archivos o inodos (~5K archivos por gen más mosaicos del H&E por versión)?
> 3. (Q13) ¿nginx tiene el módulo brotli, o solo gzip?
> 4. (Q13) ¿Cómo subo versiones (SSH/rsync) y cuántas versiones anteriores puedo conservar?
