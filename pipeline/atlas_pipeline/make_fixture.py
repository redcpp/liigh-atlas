"""Build ``fixtures/fixture/`` from the ovarian-10x canonical dataset and the raw H&E (≤ 5 MB total)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pandas as pd
import scipy.sparse as sp
import tifffile

from .adapters.common import cluster_table
from .adapters.fixture import FIXTURE_DIR
from .canonical_io import load as load_canonical
from .env import canonical_dir, raw_dir
from .he import SourceImage
from .rawio import RawFileLog

WINDOW_UM = 600.0
CORE_R = 130.0
OFFSETS = [(150.0, 150.0), (450.0, 150.0), (150.0, 450.0), (450.0, 450.0)]
PATIENTS = ["P01", "P01", "P02", "P03"]
N_GENES = 150


def make(out: Path = FIXTURE_DIR) -> dict[str, int]:
    rawlog = RawFileLog()
    src = load_canonical(canonical_dir("ovarian-10x"))
    x, y = src.cells.x_um.to_numpy(), src.cells.y_um.to_numpy()
    h, xe, ye = np.histogram2d(
        x,
        y,
        bins=[np.arange(0, x.max() + WINDOW_UM, WINDOW_UM), np.arange(0, y.max() + WINDOW_UM, WINDOW_UM)],
    )
    i, j = np.unravel_index(np.argmax(h), h.shape)
    wx0, wy0 = float(xe[i]), float(ye[j])
    keep, core_of = [], []
    for k, (ox, oy) in enumerate(OFFSETS):
        m = np.flatnonzero(np.hypot(x - wx0 - ox, y - wy0 - oy) <= CORE_R)
        keep.append(m)
        core_of += [k] * len(m)
    rows = np.concatenate(keep)
    core_of_a = np.asarray(core_of)
    sub = sp.csr_matrix(src.expression[rows])
    nnz = np.asarray((sub > 0).sum(axis=0)).ravel()
    gidx = np.sort(np.argsort(-nnz, kind="stable")[:N_GENES])
    counts = sp.csr_matrix(sub[:, gidx]).astype(np.int32)
    cells = src.cells.iloc[rows].reset_index(drop=True).copy()
    cells["x_um"] = cells.x_um - wx0
    cells["y_um"] = cells.y_um - wy0
    cells["section_id"] = "S1"
    cells["core_id"] = [f"C{k + 1:03d}" for k in core_of_a]
    cells["patient_id"] = [PATIENTS[k] for k in core_of_a]
    cells["n_transcripts"] = np.asarray(counts.sum(axis=1)).ravel().astype(np.int32)  # over the kept genes
    cores = pd.DataFrame(
        [
            {
                "core_id": f"C{k + 1:03d}",
                "section_id": "S1",
                "patient_id": PATIENTS[k],
                "kind": "core",
                "center_x_um": ox,
                "center_y_um": oy,
                "radius_um": CORE_R,
                "bbox_x0": ox - CORE_R,
                "bbox_y0": oy - CORE_R,
                "bbox_x1": ox + CORE_R,
                "bbox_y1": oy + CORE_R,
            }
            for k, (ox, oy) in enumerate(OFFSETS)
        ]
    )
    cl = src.clusters.sort_values("order")
    present = [c for c in cl.cluster_id if c in set(cells.cluster_id)]
    clusters = cluster_table(
        cells.cluster_id,
        {c: cl.set_index("cluster_id").label[c] for c in present},
        {c: cl.set_index("cluster_id").color[c] for c in present},
    )

    # H&E crop: bounding box of the window in H&E px, read from level 0 of the raw OME-TIFF
    sec = src.sections.iloc[0]
    m = np.asarray(sec.affine, float).reshape(3, 3)
    corners = np.array(
        [
            [wx0, wy0, 1],
            [wx0 + WINDOW_UM, wy0, 1],
            [wx0, wy0 + WINDOW_UM, 1],
            [wx0 + WINDOW_UM, wy0 + WINDOW_UM, 1],
        ]
    )
    pc = (m @ corners.T)[:2]
    cx0, cy0 = int(np.floor(pc[0].min())) - 32, int(np.floor(pc[1].min())) - 32
    cx1, cy1 = int(np.ceil(pc[0].max())) + 32, int(np.ceil(pc[1].max())) + 32
    he_path = rawlog.use(raw_dir("ovarian-10x") / str(sec.he_image))
    crop = SourceImage(he_path).read(0, cx0, cy0, cx1, cy1)
    out.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(
        out / "he.ome.tif",
        crop,
        tile=(256, 256),
        compression="jpeg",
        compressionargs={"level": 90},
        photometric="rgb",
        ome=True,
        metadata={"axes": "YXS", "UUID": f"urn:uuid:{uuid5(NAMESPACE_URL, f'atlas-fixture/{wx0}/{wy0}')}"},
    )
    ps = float(sec.pixel_size)
    affine_f = np.array([[1, 0, -cx0], [0, 1, -cy0], [0, 0, 1]]) @ m @ np.array([[1, 0, wx0], [0, 1, wy0], [0, 0, 1]])
    a_src = np.linalg.inv(affine_f @ np.diag([ps, ps, 1.0]))
    sections = [
        {
            "section_id": "S1",
            "he_image": "he.ome.tif",
            "affine_source": a_src.ravel().tolist(),
            "pixel_size": ps,
            "he_pixel_size_um": float(sec.he_pixel_size_um),
            "bounds_x0": 0.0,
            "bounds_y0": 0.0,
            "bounds_x1": WINDOW_UM,
            "bounds_y1": WINDOW_UM,
        }
    ]
    genes = src.genes.iloc[gidx].reset_index(drop=True)
    cells.to_parquet(out / "cells.parquet", index=False)
    genes.to_parquet(out / "genes.parquet", index=False)
    clusters.to_parquet(out / "clusters.parquet", index=False)
    cores.to_parquet(out / "cores.parquet", index=False)
    (out / "sections.json").write_text(json.dumps(sections, indent=1))
    np.savez_compressed(
        out / "counts.npz",
        data=counts.data,
        indices=counts.indices,
        indptr=counts.indptr,
        shape=np.array(counts.shape),
    )
    prov = {
        "derived_from": "ovarian-10x",
        "window_origin_um": [wx0, wy0],
        "window_um": WINDOW_UM,
        "he_crop_origin_px": [cx0, cy0],
        "n_transcripts": "row sum over the fixture's gene subset",
        "genes": f"top {N_GENES} by detection in the window",
    }
    (out / "dataset.json").write_text(json.dumps({"provenance": prov}, indent=1, sort_keys=True))
    (out / "ATTRIBUTION.md").write_text(
        "# Fixture attribution\n\nDerived from the 10x Genomics dataset *Xenium Prime FFPE Human Ovarian Cancer*\n"
        "(https://www.10xgenomics.com/datasets/xenium-prime-ffpe-human-ovarian-cancer), licensed CC BY 4.0.\n"
        "Subset: a 600 µm window, 4 cores of radius 130 µm, 150 genes, the matching H&E crop.\n"
        "Regenerate with `make fixture` (needs $DATA_ROOT).\n"
    )
    return {
        "cells": len(cells),
        "genes": len(genes),
        "clusters": len(clusters),
        "bytes": sum(f.stat().st_size for f in out.iterdir()),
    }
