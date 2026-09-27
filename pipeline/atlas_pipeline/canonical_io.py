"""Persist / load the canonical dataset (TECH_SPEC §2 stage 3): Parquet tables + AnnData counts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anndata as ad
import pandas as pd
import scipy.sparse as sp

from .contract import CanonicalDataset, DatasetRecord

TABLES = ("sections", "cores", "clusters", "genes", "cells")


def save(ds: CanonicalDataset, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        df: pd.DataFrame = getattr(ds, name)
        if name == "sections":
            (out / "sections.json").write_text(json.dumps(_records(df), indent=1))
        else:
            df.to_parquet(out / f"{name}.parquet", index=False)
    (out / "dataset.json").write_text(ds.dataset.model_dump_json(indent=1))
    adata = ad.AnnData(X=ds.expression)
    adata.obs_names = ds.cells.cell_id.to_numpy()
    adata.var_names = ds.genes.gene_id.to_numpy()
    adata.write_h5ad(out / "expression.h5ad")


def load(out: Path) -> CanonicalDataset:
    tables = {}
    for name in TABLES:
        if name == "sections":
            secs = pd.DataFrame(json.loads((out / "sections.json").read_text()))
            for col in ("he_image", "affine", "affine_source"):
                secs[col] = pd.Series([None if v is None else v for v in secs[col]], dtype=object)
            secs["he_pixel_size_um"] = pd.to_numeric(secs["he_pixel_size_um"]).astype("float64")
            tables[name] = secs
        else:
            tables[name] = pd.read_parquet(out / f"{name}.parquet")
    record = DatasetRecord.model_validate(json.loads((out / "dataset.json").read_text()))
    adata = ad.read_h5ad(out / "expression.h5ad")
    return CanonicalDataset(dataset=record, expression=sp.csr_matrix(adata.X), **tables)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Rows as plain JSON values; NaN → null (json.dumps keeps full float precision)."""
    out = []
    for rec in df.to_dict(orient="records"):
        out.append({str(k): (None if isinstance(v, float) and v != v else v) for k, v in rec.items()})
    return out
