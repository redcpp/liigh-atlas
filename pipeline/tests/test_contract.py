"""Contract validation catches each invariant (DATA_CONTRACT §8) on corrupted copies of the fixture."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from atlas_pipeline.adapters import get_adapter
from atlas_pipeline.config import load_config
from atlas_pipeline.contract import CanonicalDataset, ContractError, require_valid, validate
from atlas_pipeline.rawio import RawFileLog


@pytest.fixture(scope="module")
def ds() -> CanonicalDataset:
    return get_adapter("fixture")(load_config("fixture"), RawFileLog())


def test_fixture_is_valid(ds: CanonicalDataset) -> None:
    rep = require_valid(ds, load_config("fixture"))
    assert rep.ok and len(rep.checks) > 20


def _cells(ds: CanonicalDataset, fn: Callable[[pd.DataFrame], None]) -> CanonicalDataset:
    c = ds.cells.copy()
    fn(c)
    return dataclasses.replace(ds, cells=c)


def _cores(ds: CanonicalDataset, fn: Callable[[pd.DataFrame], None]) -> CanonicalDataset:
    c = ds.cores.copy()
    fn(c)
    return dataclasses.replace(ds, cores=c)


CASES: dict[str, Callable[[CanonicalDataset], CanonicalDataset]] = {
    "cells.cluster_id ∈ clusters": lambda d: _cells(d, lambda c: c.__setitem__("cluster_id", "ghost")),
    "cells.patient_id = cores.patient_id": lambda d: _cells(d, lambda c: c.__setitem__("patient_id", "P99")),
    "cells inside their core": lambda d: _cells(d, lambda c: c.__setitem__("x_um", c.x_um + 400)),
    "n_transcripts = counts row sum (≤ 0.1% differ)": lambda d: _cells(
        d, lambda c: c.__setitem__("n_transcripts", (c.n_transcripts + 1).astype(np.int32))
    ),
    "cores of a section do not overlap": lambda d: _cores(d, lambda c: c.__setitem__("center_x_um", 150.0)),
    "schema cells": lambda d: _cells(d, lambda c: c.__setitem__("umap_x", np.float32(np.inf))),
    "has_umap ⇔ finite UMAP coordinates": lambda d: _cells(d, lambda c: c.__setitem__("umap_y", np.float32(np.nan))),
    "schema clusters": lambda d: dataclasses.replace(d, clusters=d.clusters.assign(color="red")),
}


@pytest.mark.parametrize("rule", list(CASES))
def test_violation_is_reported(ds: CanonicalDataset, rule: str) -> None:
    bad = CASES[rule](ds)
    rep = validate(bad, load_config("fixture"))
    failed = [name for name, ok, _ in rep.checks if not ok]
    assert rule in failed
    with pytest.raises(ContractError, match="violated"):
        require_valid(bad, load_config("fixture"))
    assert "abc" not in rep.render()  # counts only, never values


def test_cells_without_embedding_are_valid(ds: CanonicalDataset) -> None:
    """General rule (Gate 1): a cell may lack an embedding if has_umap is False and its UMAP is NaN."""

    def drop(c: pd.DataFrame) -> None:
        c.loc[c.index[:5], ["umap_x", "umap_y"]] = np.float32(np.nan)
        c.loc[c.index[:5], "has_umap"] = False

    rep = validate(_cells(ds, drop), load_config("fixture"))
    assert rep.ok, rep.render()
    assert "5 cells without embedding" in rep.render()


def test_known_totals_from_config(ds: CanonicalDataset) -> None:
    cfg = load_config("fixture").model_copy(update={"expected": load_config("scale").expected})
    failed = {n for n, ok, _ in validate(ds, cfg).checks if not ok}
    assert {"cells ≥ 443000", "cores ≥ 100", "patients = 62", "sections = 3", "clusters = 23"} <= failed
    cfg2 = load_config("fixture").model_copy(update={"expected": load_config("ovarian-10x").expected})
    failed2 = {n for n, ok, _ in validate(ds, cfg2).checks if not ok}
    assert "cells = 407124" in failed2 and "median transcripts/cell = 178" in failed2
