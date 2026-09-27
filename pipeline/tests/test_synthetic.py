"""synthetic-tma / scale derivation on a small seeded tissue (T-PIPE-CONTRACT-02 logic, unit scale)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from atlas_pipeline.adapters import get_adapter, synthetic
from atlas_pipeline.config import load_config
from atlas_pipeline.contract import CanonicalDataset, DatasetRecord, validate


def toy_tissue(n: int = 30_000, side: float = 5_000.0, seed: int = 0) -> CanonicalDataset:
    rng = np.random.default_rng(seed)
    x, y = rng.uniform(0, side, n), rng.uniform(0, side, n)
    groups = np.array(["a", "b", "c", "unassigned"])[rng.choice(4, n, p=[0.5, 0.3, 0.15, 0.05])]
    counts = sp.random(n, 40, density=0.2, format="csr", random_state=seed, data_rvs=lambda k: rng.integers(1, 9, k))
    counts = counts.astype(np.int32)
    cells = pd.DataFrame(
        {
            "cell_id": [f"c{i}" for i in range(n)],
            "section_id": "S1",
            "core_id": "S1-region",
            "patient_id": "P01",
            "x_um": x,
            "y_um": y,
            "umap_x": rng.normal(size=n).astype(np.float32),
            "umap_y": rng.normal(size=n).astype(np.float32),
            "cluster_id": groups,
            "n_transcripts": np.asarray(counts.sum(axis=1)).ravel().astype(np.int32),
        }
    )
    clusters = pd.DataFrame(
        {
            "cluster_id": ["a", "b", "c", "unassigned"],
            "label": ["A", "B", "C", "Unassigned"],
            "color": ["#112233", "#445566", "#778899", "#F2F2F2"],
            "order": np.arange(4, dtype=np.int16),
            "n_cells": np.array([(groups == g).sum() for g in "abc"] + [(groups == "unassigned").sum()], np.int32),
        }
    )
    genes = pd.DataFrame(
        {
            "gene_id": [f"G{i}" for i in range(40)],
            "symbol": [f"g{i}" for i in range(40)],
            "panel": "predesigned",
        }
    )
    sections = pd.DataFrame(
        [
            {
                "section_id": "S1",
                "he_image": None,
                "affine": None,
                "affine_source": None,
                "pixel_size": 0.2125,
                "he_pixel_size_um": None,
                "bounds_x0": 0.0,
                "bounds_y0": 0.0,
                "bounds_x1": side,
                "bounds_y1": side,
            }
        ]
    )
    rec = DatasetRecord(
        name="toy",
        title="t",
        license="CC-BY-4.0",
        citation="c",
        provenance={},
        synthetic=False,
        visibility="public",
    )
    return CanonicalDataset(rec, sections, pd.DataFrame(), clusters, genes, cells, counts)


def test_synthetic_tma_from_toy() -> None:
    cfg = load_config("synthetic-tma").model_copy(
        update={"expected": load_config("synthetic-tma").expected.model_copy(update={"n_clusters": 4})}
    )
    ds = synthetic.derive(toy_tissue(), cfg)
    rep = validate(ds, cfg)
    assert rep.ok, rep.render()
    per_patient = ds.cores.groupby("patient_id").size()
    assert len(ds.cores) >= 4 and (per_patient >= 2).any() and ds.dataset.synthetic
    assert ds.expression.shape == (len(ds.cells), 40)


def test_scale_replicates_and_splits() -> None:
    base = load_config("scale")
    cfg = base.model_copy(
        update={
            "target_cells": 60_000,
            "min_cores": 20,
            "n_patients": 7,
            "split_largest": 2,
            "expected": base.expected.model_copy(
                update={"min_cells": 60_000, "min_cores": 20, "n_patients": 7, "n_clusters": 6}
            ),
        }
    )
    ds = synthetic.derive(toy_tissue(), cfg)
    rep = validate(ds, cfg)
    assert rep.ok, rep.render()
    assert ds.cells.cell_id.str.contains("-r").any()
    assert {"a-sub-1", "a-sub-2", "b-sub-1", "b-sub-2"} <= set(ds.clusters.cluster_id)
    assert ds.clusters.set_index("cluster_id").label["a-sub-2"] == "A · sub 2"
    assert synthetic.shade("#FFFFFF") == "#8C8C8C"


def test_assign_patients_needs_enough_cores() -> None:
    with pytest.raises(ValueError):
        synthetic.assign_patients(3, 5, np.random.default_rng(0))


def test_synthetic_needs_source(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS_ALLOW_UNMOUNTED_DATA_ROOT", "1")
    from atlas_pipeline.rawio import RawFileLog

    with pytest.raises(FileNotFoundError, match="make pipeline DATASET=ovarian-10x"):
        get_adapter("synthetic-tma")(load_config("synthetic-tma"), RawFileLog())
    with pytest.raises(KeyError):
        get_adapter("nope")
