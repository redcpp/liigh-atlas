"""Canonical data contract (docs/DATA_CONTRACT.md): types, schemas and cross-entity invariants.

Violations fail loudly with entity, rule and count of bad rows; values are never printed so the same
report is safe for private datasets (DATA_CONTRACT §8.6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
import pandera.pandas as pa
import scipy.sparse as sp
from pydantic import BaseModel, ConfigDict

from .config import DatasetConfig


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    title: str
    license: str
    citation: str
    provenance: dict[str, Any]
    synthetic: bool
    visibility: Literal["public", "private"]
    release: str = ""


@dataclass(frozen=True)
class CanonicalDataset:
    dataset: DatasetRecord
    sections: pd.DataFrame
    cores: pd.DataFrame
    clusters: pd.DataFrame
    genes: pd.DataFrame
    cells: pd.DataFrame
    expression: sp.csr_matrix  # counts, int32, rows = cells, cols = genes


class ContractError(ValueError):
    pass


_str = pa.Column(str, nullable=False)

CELLS = pa.DataFrameSchema(
    {
        "cell_id": pa.Column(str, unique=True, nullable=False),
        "section_id": _str,
        "core_id": _str,
        "patient_id": _str,
        "x_um": pa.Column("float64", pa.Check(lambda s: np.isfinite(s)), nullable=False),
        "y_um": pa.Column("float64", pa.Check(lambda s: np.isfinite(s)), nullable=False),
        "umap_x": pa.Column("float32", pa.Check(lambda s: np.isfinite(s)), nullable=False),
        "umap_y": pa.Column("float32", pa.Check(lambda s: np.isfinite(s)), nullable=False),
        "cluster_id": _str,
        "n_transcripts": pa.Column("int32", pa.Check.ge(0), nullable=False),
    },
    strict=True,
    ordered=True,
)
GENES = pa.DataFrameSchema(
    {
        "gene_id": pa.Column(str, unique=True, nullable=False),
        "symbol": _str,
        "panel": pa.Column(str, pa.Check.isin(["predesigned", "custom"]), nullable=False),
    },
    strict=True,
    ordered=True,
)
CLUSTERS = pa.DataFrameSchema(
    {
        "cluster_id": pa.Column(str, unique=True, nullable=False),
        "label": _str,
        "color": pa.Column(str, pa.Check.str_matches(r"^#[0-9A-Fa-f]{6}$"), nullable=False),
        "order": pa.Column("int16", unique=True, nullable=False),
        "n_cells": pa.Column("int32", pa.Check.ge(0), nullable=False),
    },
    strict=True,
    ordered=True,
)
CORES = pa.DataFrameSchema(
    {
        "core_id": pa.Column(str, unique=True, nullable=False),
        "section_id": _str,
        "patient_id": pa.Column(str, pa.Check.str_matches(r"^P\d{2,}$"), nullable=False),
        "kind": pa.Column(str, pa.Check.isin(["core", "region"]), nullable=False),
        "center_x_um": pa.Column("float64"),
        "center_y_um": pa.Column("float64"),
        "radius_um": pa.Column("float64", pa.Check.gt(0)),
        "bbox_x0": pa.Column("float64"),
        "bbox_y0": pa.Column("float64"),
        "bbox_x1": pa.Column("float64"),
        "bbox_y1": pa.Column("float64"),
    },
    strict=True,
    ordered=True,
)
SECTIONS = pa.DataFrameSchema(
    {
        "section_id": pa.Column(str, unique=True, nullable=False),
        "he_image": pa.Column(object, nullable=True),
        "affine": pa.Column(object, nullable=True),
        "affine_source": pa.Column(object, nullable=True),
        "pixel_size": pa.Column("float64", pa.Check.gt(0)),
        "he_pixel_size_um": pa.Column("float64", nullable=True),
        "bounds_x0": pa.Column("float64"),
        "bounds_y0": pa.Column("float64"),
        "bounds_x1": pa.Column("float64"),
        "bounds_y1": pa.Column("float64"),
    },
    strict=True,
    ordered=True,
)


@dataclass
class Report:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, bool(ok), detail))

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def render(self) -> str:
        lines = [f"  [{'ok' if ok else 'FAIL'}] {name}" + (f" — {d}" if d else "") for name, ok, d in self.checks]
        return "\n".join(lines)


def _schema(report: Report, name: str, schema: pa.DataFrameSchema, df: pd.DataFrame) -> None:
    try:
        schema.validate(df, lazy=True)
        report.add(f"schema {name}", True, f"{len(df)} rows")
    except (pa.errors.SchemaErrors, pa.errors.SchemaError) as exc:
        cases = getattr(exc, "failure_cases", None)
        n = len(cases) if cases is not None else 1
        checks = sorted(set(cases["check"].astype(str))) if cases is not None else [str(exc)[:80]]
        report.add(f"schema {name}", False, f"{n} failure case(s): {', '.join(checks)[:300]}")


def validate(ds: CanonicalDataset, cfg: DatasetConfig) -> Report:
    r = Report()
    _schema(r, "cells", CELLS, ds.cells)
    _schema(r, "genes", GENES, ds.genes)
    _schema(r, "clusters", CLUSTERS, ds.clusters)
    _schema(r, "cores", CORES, ds.cores)
    _schema(r, "sections", SECTIONS, ds.sections)
    cells, cores, secs = ds.cells, ds.cores, ds.sections

    # 1. referential integrity
    r.add("cells.section_id ∈ sections", int((~cells.section_id.isin(secs.section_id)).sum()) == 0)
    r.add("cells.core_id ∈ cores", int((~cells.core_id.isin(cores.core_id)).sum()) == 0)
    r.add("cells.cluster_id ∈ clusters", int((~cells.cluster_id.isin(ds.clusters.cluster_id)).sum()) == 0)
    r.add("cores.section_id ∈ sections", int((~cores.section_id.isin(secs.section_id)).sum()) == 0)
    shape_ok = ds.expression.shape == (len(cells), len(ds.genes))
    r.add("expression shape = cells × genes", shape_ok, f"{ds.expression.shape}")
    r.add("expression dtype int32, ≥ 0", ds.expression.dtype == np.int32 and (ds.expression.data >= 0).all())
    lower = ds.genes.symbol.str.lower()
    r.add("genes.symbol unique (case-insensitive)", not lower.duplicated().any())

    # 2. patient consistency and non-empty cores
    core_idx = cores.set_index("core_id")
    joined = core_idx.reindex(cells.core_id)
    bad_pat = int((joined.patient_id.to_numpy() != cells.patient_id.to_numpy()).sum())
    bad_sec = int((joined.section_id.to_numpy() != cells.section_id.to_numpy()).sum())
    r.add("cells.patient_id = cores.patient_id", bad_pat == 0, f"{bad_pat} bad rows")
    r.add("cells.section_id = core.section_id", bad_sec == 0, f"{bad_sec} bad rows")
    empty = int((~cores.core_id.isin(cells.core_id.unique())).sum())
    r.add("every core has ≥ 1 cell", empty == 0, f"{empty} empty cores")

    # 3. spatial containment
    x, y = cells.x_um.to_numpy(), cells.y_um.to_numpy()
    kind = joined.kind.to_numpy()
    d = np.hypot(x - joined.center_x_um.to_numpy(), y - joined.center_y_um.to_numpy())
    in_radius = d <= joined.radius_um.to_numpy() + 50.0
    in_bbox = (
        (x >= joined.bbox_x0.to_numpy())
        & (x <= joined.bbox_x1.to_numpy())
        & (y >= joined.bbox_y0.to_numpy())
        & (y <= joined.bbox_y1.to_numpy())
    )
    bad_core = int((~np.where(kind == "core", in_radius & in_bbox, in_bbox)).sum())
    r.add("cells inside their core", bad_core == 0, f"{bad_core} bad rows")
    sec_idx = secs.set_index("section_id")
    sj = sec_idx.reindex(cells.section_id)
    bad_sec_b = int(
        (
            ~(
                (x >= sj.bounds_x0.to_numpy())
                & (x <= sj.bounds_x1.to_numpy())
                & (y >= sj.bounds_y0.to_numpy())
                & (y <= sj.bounds_y1.to_numpy())
            )
        ).sum()
    )
    r.add("cells inside section bounds", bad_sec_b == 0, f"{bad_sec_b} bad rows")
    cs = sec_idx.reindex(cores.section_id)
    core_in = (
        (cores.bbox_x0.to_numpy() >= cs.bounds_x0.to_numpy())
        & (cores.bbox_y0.to_numpy() >= cs.bounds_y0.to_numpy())
        & (cores.bbox_x1.to_numpy() <= cs.bounds_x1.to_numpy())
        & (cores.bbox_y1.to_numpy() <= cs.bounds_y1.to_numpy())
    )
    r.add("cores inside section bounds", bool(core_in.all()), f"{int((~core_in).sum())} bad cores")
    r.add("cores of a section do not overlap", _no_overlap(cores))

    # sections: affine required with an image, invertible, last row [0,0,1]
    aff_ok = True
    for _, s in secs.iterrows():
        if s.he_image is not None:
            a = np.asarray(s.affine, dtype=float).reshape(3, 3) if s.affine is not None else None
            aff_ok &= a is not None and bool(np.allclose(a[2], [0, 0, 1])) and abs(np.linalg.det(a)) > 1e-12
            aff_ok &= s.affine_source is not None and s.he_pixel_size_um is not None
    r.add("sections with H&E have an invertible affine + source affine", aff_ok)

    # 4. counts
    row_sum = np.asarray(ds.expression.sum(axis=1)).ravel()
    disagree = float(np.mean(row_sum != cells.n_transcripts.to_numpy())) if len(cells) else 0.0
    r.add("n_transcripts = counts row sum (≤ 0.1% differ)", disagree <= 0.001, f"{disagree:.4%} differ")
    observed = cells.cluster_id.value_counts()
    nc = ds.clusters.set_index("cluster_id").n_cells
    r.add("clusters.n_cells = observed", bool((observed.reindex(nc.index, fill_value=0) == nc).all()))

    # 5. known totals from config
    e = cfg.expected
    n_cells = len(cells)
    med = float(np.median(cells.n_transcripts)) if n_cells else 0.0
    if e.n_cells is not None:
        r.add(f"cells = {e.n_cells}", n_cells == e.n_cells, f"{n_cells}")
    if e.min_cells is not None:
        r.add(f"cells ≥ {e.min_cells}", n_cells >= e.min_cells, f"{n_cells}")
    if e.median_transcripts is not None:
        r.add(f"median transcripts/cell = {e.median_transcripts:g}", med == e.median_transcripts, f"{med:g}")
    if e.n_clusters is not None:
        r.add(f"clusters = {e.n_clusters}", len(ds.clusters) == e.n_clusters, f"{len(ds.clusters)}")
    if e.min_cores is not None:
        r.add(f"cores ≥ {e.min_cores}", len(cores) >= e.min_cores, f"{len(cores)}")
    if e.n_patients is not None:
        n_p = cores.patient_id.nunique()
        r.add(f"patients = {e.n_patients}", n_p == e.n_patients, f"{n_p}")
    if e.n_sections is not None:
        r.add(f"sections = {e.n_sections}", len(secs) == e.n_sections, f"{len(secs)}")
    r.add("dataset.name matches config", ds.dataset.name == cfg.name)
    return r


def _no_overlap(cores: pd.DataFrame) -> bool:
    for _, grp in cores[cores.kind == "core"].groupby("section_id"):
        c = grp[["center_x_um", "center_y_um"]].to_numpy()
        rad = grp.radius_um.to_numpy()
        if len(c) < 2:
            continue
        dist = np.hypot(c[:, None, 0] - c[None, :, 0], c[:, None, 1] - c[None, :, 1])
        np.fill_diagonal(dist, np.inf)
        if (dist < rad[:, None] + rad[None, :]).any():
            return False
    return True


def require_valid(ds: CanonicalDataset, cfg: DatasetConfig) -> Report:
    report = validate(ds, cfg)
    if not report.ok:
        raise ContractError("canonical data contract violated:\n" + report.render())
    return report
