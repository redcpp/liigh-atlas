"""Helpers shared by adapters."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

NDArrayF = NDArray[Any]


def he_affine(align_source: NDArray[Any], pixel_size: float) -> NDArray[Any]:
    """µm → H&E px = inverse(A_align) · diag(1/pixel_size, 1/pixel_size, 1) (DATA_CONTRACT §6).

    ``A_align`` is the Xenium Explorer alignment matrix, which maps H&E px → Xenium px.
    """
    um_to_xpx = np.diag([1.0 / pixel_size, 1.0 / pixel_size, 1.0])
    return np.asarray(np.linalg.inv(align_source) @ um_to_xpx)


def he_pixel_size_um(align_source: NDArray[Any], pixel_size: float) -> float:
    """Side of one H&E pixel in µm: sqrt(|det| of the linear part) × Xenium pixel size."""
    return float(np.sqrt(abs(np.linalg.det(align_source[:2, :2]))) * pixel_size)


def region_core(section_id: str, patient_id: str, x: NDArray[Any], y: NDArray[Any]) -> dict[str, object]:
    x0, y0, x1, y1 = (
        float(np.floor(x.min())),
        float(np.floor(y.min())),
        float(np.ceil(x.max())),
        float(np.ceil(y.max())),
    )
    return {
        "core_id": f"{section_id}-region",
        "section_id": section_id,
        "patient_id": patient_id,
        "kind": "region",
        "center_x_um": (x0 + x1) / 2,
        "center_y_um": (y0 + y1) / 2,
        "radius_um": max(x1 - x0, y1 - y0) / 2,
        "bbox_x0": x0,
        "bbox_y0": y0,
        "bbox_x1": x1,
        "bbox_y1": y1,
    }


def dedupe_symbols(symbols: list[str]) -> tuple[list[str], int]:
    """Make symbols unique case-insensitively by suffixing ``-2``, ``-3`` …"""
    seen: dict[str, int] = {}
    out: list[str] = []
    n_dup = 0
    for s in symbols:
        k = s.lower()
        if k in seen:
            seen[k] += 1
            out.append(f"{s}-{seen[k]}")
            n_dup += 1
        else:
            seen[k] = 1
            out.append(s)
    return out, n_dup


def cluster_table(cells_cluster: pd.Series, labels: dict[str, str], colors: dict[str, str]) -> pd.DataFrame:
    ids = list(labels)
    counts = cells_cluster.value_counts()
    return pd.DataFrame(
        {
            "cluster_id": ids,
            "label": [labels[i] for i in ids],
            "color": [colors[i].upper() for i in ids],
            "order": np.arange(len(ids), dtype=np.int16),
            "n_cells": np.array([int(counts.get(i, 0)) for i in ids], dtype=np.int32),
        }
    )


def slug(label: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in label)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")
