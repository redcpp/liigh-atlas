"""T-PIPE-UMAP-01 (unit part): coherence score, selection rule, cache hit on the second run."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from atlas_pipeline import umap_select as us
from atlas_pipeline.config import load_config
from atlas_pipeline.rawio import RawFileLog


def test_knn_coherence_separated_vs_mixed() -> None:
    rng = np.random.default_rng(0)
    lab = np.repeat([0, 1], 200)
    sep = np.concatenate([rng.normal(0, 0.1, (200, 2)), rng.normal(10, 0.1, (200, 2))])
    assert us.knn_coherence(sep, lab) == 1.0
    assert 0.3 < us.knn_coherence(rng.normal(size=(400, 2)), lab) < 0.7
    dup = np.zeros((20, 2))  # duplicates: self may not be in column 0
    assert us.knn_coherence(dup, np.zeros(20)) == 1.0


def test_select_and_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS_ALLOW_UNMOUNTED_DATA_ROOT", "1")
    rng = np.random.default_rng(1)
    n = 300
    ids = np.array([f"c{i}" for i in range(n)])
    labels = np.where(np.arange(n) < 150, "a", "unassigned")
    counts = sp.csr_matrix(rng.integers(1, 5, (n, 8)).astype(np.int32))
    counts[0] = 0  # a zero-transcript cell, absent from the provided UMAP
    counts.eliminate_zeros()
    outs = tmp_path / "outs"
    proj = outs / "analysis/umap/gene_expression_2_components"
    proj.mkdir(parents=True)
    good = np.where(labels[:, None] == "a", 0.0, 10.0) + rng.normal(0, 0.1, (n, 2))
    pd.DataFrame({"Barcode": ids[1:], "UMAP-1": good[1:, 0], "UMAP-2": good[1:, 1]}).to_csv(
        proj / "projection.csv", index=False
    )
    calls: list[int] = []

    def fake(c: sp.csr_matrix, seed: int) -> np.ndarray:
        calls.append(c.shape[0])
        return np.random.default_rng(seed).normal(size=(c.shape[0], 2)).astype(np.float32)

    monkeypatch.setattr(us, "recompute_umap", fake)
    cfg = load_config("ovarian-10x")
    emb, prov = us.select_umap(counts, ids, labels, outs, cfg, RawFileLog())
    assert prov["source"] == "provided" and prov["zero_transcript_cells_placed_at_group_median"] == 1
    assert prov["knn_coherence"]["provided"] > prov["knn_coherence"]["recomputed"]
    assert np.isfinite(emb).all() and calls == [n - 1]
    emb2, prov2 = us.select_umap(counts, ids, labels, outs, cfg, RawFileLog())
    assert calls == [n - 1], "second run must reuse the cache"
    assert np.array_equal(emb, emb2) and prov == prov2
    sidecar = next((tmp_path / "derived/ovarian-10x").glob("umap-*.json")).read_text()
    assert "input_matrix_sha256" in sidecar and "scanpy" in sidecar
