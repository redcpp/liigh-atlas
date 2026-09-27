"""`ovarian-10x` adapter: Xenium outs/ + 10x supplemental files → canonical dataset."""

from __future__ import annotations

import json
import logging

import h5py
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import scipy.sparse as sp

from .. import PIPELINE_VERSION
from ..config import DatasetConfig
from ..contract import CanonicalDataset, DatasetRecord
from ..env import raw_dir
from ..rawio import RawFileLog
from ..umap_select import select_umap
from ..verify import SUPP_PREFIX, parse_md5
from .common import cluster_table, dedupe_symbols, he_affine, he_pixel_size_um, region_core, slug

log = logging.getLogger(__name__)
ADAPTER_VERSION = "1"
SECTION = "S1"
PATIENT = "P01"


def load(cfg: DatasetConfig, rawlog: RawFileLog) -> CanonicalDataset:
    root = raw_dir("ovarian-10x")
    outs, supp = root / "outs", root / "supplemental"

    experiment = json.loads(rawlog.use(outs / "experiment.xenium").read_text())
    pixel_size = float(experiment["pixel_size"])

    cells_pq = pq.read_table(
        rawlog.use(outs / "cells.parquet"),
        columns=["cell_id", "x_centroid", "y_centroid", "transcript_counts"],
    ).to_pandas()

    with h5py.File(rawlog.use(outs / "cell_feature_matrix.h5"), "r") as f:
        m = f["matrix"]
        barcodes = m["barcodes"][:].astype(str)
        ftype = m["features/feature_type"][:].astype(str)
        fid = m["features/id"][:].astype(str)
        fname = m["features/name"][:].astype(str)
        n_rows, n_cols = (int(v) for v in m["shape"][:])  # features × cells
        csc = sp.csc_matrix(
            (m["data"][:].astype(np.int32), m["indices"][:].astype(np.int32), m["indptr"][:]),
            shape=(n_rows, n_cols),
        )
    is_gene = ftype == "Gene Expression"
    counts = csc[is_gene].T.tocsr().astype(np.int32)  # cells × genes
    counts.sort_indices()
    log.info(
        "features: %d total, %d genes, %d controls/codewords dropped",
        len(ftype),
        is_gene.sum(),
        (~is_gene).sum(),
    )

    panel = json.loads(rawlog.use(outs / "gene_panel.json").read_text())
    category = {
        t["type"]["data"]["id"]: t["source"]["category"]
        for t in panel["payload"]["targets"]
        if t["type"]["descriptor"] == "gene" and "id" in t["type"]["data"]
    }
    symbols, n_dup = dedupe_symbols(list(fname[is_gene]))
    genes = pd.DataFrame(
        {
            "gene_id": fid[is_gene],
            "symbol": symbols,
            "panel": ["predesigned" if category.get(g) == "base" else "custom" for g in fid[is_gene]],
        }
    )
    log.info(
        "genes: %d predesigned, %d custom, %d symbols deduplicated",
        (genes.panel == "predesigned").sum(),
        (genes.panel == "custom").sum(),
        n_dup,
    )

    # align the matrix to cells.parquet order
    pos = pd.Index(barcodes).get_indexer(cells_pq.cell_id)
    if (pos < 0).any():
        raise ValueError(f"{int((pos < 0).sum())} cells missing from the matrix")
    counts = counts[pos]

    groups = pd.read_csv(rawlog.use(supp / f"{SUPP_PREFIX}cell_groups.csv"))
    label_by_cell = groups.set_index("cell_id").group.reindex(cells_pq.cell_id)
    missing = label_by_cell.isna().to_numpy()
    if missing.any():
        # 10x leaves cells that Seurat filtered out (all have 0 transcripts) out of the CSV;
        # they belong to 10x's own "Unassigned" group. Never invent another label.
        zero = cells_pq.transcript_counts.to_numpy()[missing] == 0
        if not zero.all() or "Unassigned" not in set(groups.group):
            raise ValueError(f"{int(missing.sum())} cells have no 10x cell group")
        log.info("cells without a 10x group (0 transcripts) -> Unassigned: %d", int(missing.sum()))
        label_by_cell = label_by_cell.fillna("Unassigned")
    sizes = groups.group.value_counts()
    ordered_groups = sorted(sizes.index, key=lambda g: (g.lower() == "unassigned", -int(sizes[g]), g))
    color_of = groups.drop_duplicates("group").set_index("group").color
    ordered = pd.DataFrame({"group": ordered_groups, "color": [color_of[g] for g in ordered_groups]})
    labels = {slug(g): g for g in ordered.group}
    colors = {slug(g): c for g, c in zip(ordered.group, ordered.color, strict=True)}
    cluster_id = label_by_cell.map(slug).to_numpy()

    x = cells_pq.x_centroid.to_numpy(np.float64)
    y = cells_pq.y_centroid.to_numpy(np.float64)
    umap, umap_prov = select_umap(counts, cells_pq.cell_id.to_numpy(), cluster_id, outs, cfg, rawlog)

    cells = pd.DataFrame(
        {
            "cell_id": cells_pq.cell_id.astype(str).to_numpy(),
            "section_id": SECTION,
            "core_id": f"{SECTION}-region",
            "patient_id": PATIENT,
            "x_um": x,
            "y_um": y,
            "umap_x": umap[:, 0].astype(np.float32),
            "umap_y": umap[:, 1].astype(np.float32),
            "cluster_id": cluster_id,
            "n_transcripts": cells_pq.transcript_counts.to_numpy().astype(np.int32),
        }
    )
    cores = pd.DataFrame([region_core(SECTION, PATIENT, x, y)])

    align_path = supp / f"{SUPP_PREFIX}he_imagealignment.csv"
    a_src = np.loadtxt(rawlog.use(align_path), delimiter=",")
    he_rel = f"supplemental/{SUPP_PREFIX}he_image.ome.tif"
    sections = pd.DataFrame(
        [
            {
                "section_id": SECTION,
                "he_image": he_rel,
                "affine": he_affine(a_src, pixel_size).ravel().tolist(),
                "affine_source": a_src.ravel().tolist(),
                "pixel_size": pixel_size,
                "he_pixel_size_um": he_pixel_size_um(a_src, pixel_size),
                "bounds_x0": 0.0,
                "bounds_y0": 0.0,
                "bounds_x1": float(np.ceil(x.max())),
                "bounds_y1": float(np.ceil(y.max())),
            }
        ]
    )
    md5 = parse_md5(rawlog.use(supp / "md5.expected").read_text())
    record = DatasetRecord(
        name=cfg.name,
        title=cfg.title,
        license=cfg.license,
        citation=cfg.citation,
        synthetic=cfg.synthetic,
        visibility=cfg.visibility,
        provenance={
            "source_url": "https://www.10xgenomics.com/datasets/xenium-prime-ffpe-human-ovarian-cancer",
            "md5": md5,
            "adapter": f"ovarian-10x@{ADAPTER_VERSION}",
            "pipeline_version": PIPELINE_VERSION,
            "xenium_analysis": experiment.get("analysis_sw_version"),
            "pixel_size_um": pixel_size,
            "normalization": {"method": cfg.normalization, "scale_factor": cfg.scale_factor},
            "seed": cfg.seed,
            "umap": umap_prov,
            "clusters_source": "10x Cell Groups CSV (Seurat v5)",
        },
    )
    return CanonicalDataset(
        dataset=record,
        sections=sections,
        cores=cores,
        clusters=cluster_table(pd.Series(cluster_id), labels, colors),
        genes=genes,
        cells=cells,
        expression=counts,
    )
