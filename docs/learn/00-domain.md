# 00 — Domain primer for the maintainer

Each concept in 3–5 lines with an analogy, then used in the next one. Numbers come from the dev dataset
(10x Xenium Prime FFPE Human Ovarian Cancer) as measured on `$DATA_ROOT`.

## 1. In situ transcriptomics (Xenium)
Xenium detects individual RNA molecules directly in a thin tissue slice and records where each one is:
(x, y) in µm plus which gene it came from. The dev run has 120,455,566 high-quality transcripts over
86.8 mm² of tissue.
**Analogy:** a satellite photo where every lit window is tagged with the name of who lives there.

## 2. Gene panel
Xenium does not read every gene; it reads a fixed list of probes. Prime 5K has 5,001 predesigned genes;
the dev run adds 100 custom ones (5,101 gene features), plus control probes we drop.
**Analogy:** a census that only asks 5,000 fixed questions; if a question is not on the form, the
answer does not exist in the data.

## 3. Segmentation
Software draws a boundary around each cell (from nucleus and membrane stains) and assigns each
transcript to the cell it falls in. Result: 407,124 cells; 88.4% of transcripts land in a cell.
**Analogy:** drawing property lines on the satellite photo, then counting each house's windows.

## 4. Cell × gene count matrix (sparse)
Counting transcripts per (cell, gene) gives a 407,124 × 5,101 matrix. Most entries are 0: 80.5M
non-zeros out of 2.08 billion cells ≈ 3.9% density, so it is stored sparse (only non-zeros).
**Analogy:** a spreadsheet of who bought what in a supermarket; almost every cell is empty, so you
keep a receipt list instead of the whole grid.

## 5. Normalization (log1p of counts per 10K)
Big cells capture more transcripts, so raw counts mix "more of this gene" with "bigger cell". Dividing
by the cell's total, scaling to 10,000 and taking `log(1 + x)` compares cells fairly and tames outliers.
**Analogy:** comparing household spending as a share of income, on a log scale so millionaires do not
flatten everyone else.

## 6. Clustering and annotation
Cells with similar expression profiles are grouped (graph clustering, e.g. Seurat resolution 0.6) and
experts name the groups by marker genes ("Macrophages", "T and NK Cells"). Dev data: 18 groups; lab
data: 23 annotated clusters. Names come from the data, never invented by us.
**Analogy:** sorting a pile of books by the words they share, then a librarian labels each shelf.

## 7. UMAP: the second position of every cell
UMAP squeezes each cell's 5K-dimensional profile into 2D so similar cells land close. Every cell thus
has two positions: physical (x, y µm, where it lives) and similarity (UMAP, who it resembles). Distances
in UMAP are not µm and not even globally meaningful; only neighborhoods are.
**Analogy:** a seating chart at a wedding grouped by friendship versus the map of where guests live;
the atlas's value is pointing at a table and seeing the houses light up, and vice versa.

## 8. H&E
A classic pathology stain photographed from the same section after Xenium: hematoxylin colors nuclei
purple-blue, eosin colors cytoplasm and matrix pink. It is a separate image with its own pixels.
**Analogy:** a hand-drawn tourist map of the same city: familiar to pathologists, but on its own grid.

## 9. Alignment: an affine chain
To put a cell on the H&E: µm ÷ 0.2125 → Xenium morphology pixels → inverse of the 3×3 alignment
affine → H&E pixels. The dev affine rotates ~90° and scales ≈ 1.29 (H&E px → Xenium px), so one H&E
pixel ≈ 0.274 µm. Direction mistakes produce plausible-looking garbage, so it is tested (nuclei are
darker in hematoxylin exactly where cell centroids fall).
**Analogy:** converting street addresses to GPS to pixel on a rotated scanned map; one wrong
direction and every pin lands in a lake.

## 10. TMA hierarchy
A tissue microarray is one slide with a grid of ~1 mm cores punched from different patients' tumors.
Hierarchy: section (slide/run) → core → cell; a patient may have several cores; one Xenium run covers
~35 patients.
**Analogy:** a muffin tray: the tray is the section, each muffin a core, and one baker (patient) may
have made two muffins.

## 11. Image pyramids and tiles
A gigapixel H&E cannot be sent whole. It is cut into 512 px tiles at several zoom levels, each half
the resolution of the previous; the browser fetches only the tiles on screen at the current zoom.
**Analogy:** web maps: zoomed out you get one country tile, zoomed in you only download your street.

## 12. Quantization
Storing a coordinate as a 16-bit integer plus a scale instead of a 32-bit float halves the bytes. The
cost is a step size: 11,481 µm / 65,535 ≈ 0.18 µm for dev tissue, far below a ~10 µm cell.
**Analogy:** measuring a room with a ruler marked every 0.2 mm instead of a laser: for furniture
placement you will never notice.

## 13. Color-blind-safe palettes
About 1 in 12 men has a red-green deficiency (protan/deutan). With 23 clusters, colors must stay
distinguishable under simulated deficiency, and color is never the only cue: labels and hover
highlights carry the same information.
**Analogy:** a subway map that also prints line numbers, so nobody depends on telling red from green.

## What you must be able to re-derive without notes

1. **µm → H&E px for a cell:** `p = (x/0.2125, y/0.2125, 1)`, `h = A⁻¹ p` with `A` the alignment CSV
   (H&E px → Xenium px); explain why the inverse, and how the hematoxylin test catches a wrong direction.
2. **Initial payload:** 443K × 2 × 4 B = 3.54 MB (float32 UMAP) vs 1.77 MB (uint16); plus 0.44 MB of
   `uint8` cluster ids; why that decides NFR-3 (< 5 MB).
3. **Sparse vs dense break-even:** sparse ≈ 3 B per non-zero, dense 1 B per cell → sparse wins below
   ~33% density; average dev gene ≈ 15.8K non-zeros ≈ 47 KB vs 407 KB dense.
4. **Expression total:** 80.5M non-zeros × 3 B ≈ 240 MB; 5K genes × 0.44 MB dense ≈ 2.2 GB worst case.
5. **Cores in the dev tissue:** 86.8 mm² / 0.785 mm² ≈ 110 by area alone; packing, tissue gaps and
   the ≥ 80% coverage rule leave a few dozen → the `scale` dataset must replicate cores.
6. **Mean vs median transcripts per cell:** 120.5M × 0.884 / 407,124 ≈ 262 mean vs 178 median →
   right-skewed; a few large cells carry many transcripts.
7. **Why UMAP distance ≠ physical distance**, and why linking both spaces is the product's core value.
8. **Why 18 dev groups become 23 in `scale`:** split the 5 largest groups in two (18 + 5 = 23), with
   generic labels, never invented biology.
