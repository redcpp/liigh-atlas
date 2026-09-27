"""Integration tests on the real development data; skipped when $DATA_ROOT is not mounted.

T-PIPE-DATA-01, T-PIPE-CONTRACT-01, T-PIPE-CONTRACT-02, T-PIPE-ALIGN-01, T-PIPE-ALIGN-02,
T-PIPE-QUANT-01, T-PIPE-UMAP-01, T-PIPE-SIZE-01.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from atlas_pipeline import align, assets
from atlas_pipeline.canonical_io import load as load_canonical
from atlas_pipeline.config import load_config
from atlas_pipeline.contract import require_valid
from atlas_pipeline.env import build_dir, canonical_dir, derived_dir, raw_dir
from atlas_pipeline.he import SourceImage, TileReader
from atlas_pipeline.verify import verify

from .conftest import requires_data

pytestmark = [pytest.mark.data, requires_data]


def current(name: str) -> Path:
    p = build_dir(name) / "current.json"
    if not p.exists():
        pytest.skip(f"{name} not built yet: make pipeline DATASET={name}")
    return build_dir(name) / json.loads(p.read_text())["release"]


def test_data_verify_idempotent() -> None:
    before = sorted(p.name for p in raw_dir("ovarian-10x").rglob("*"))
    checks = verify(
        raw_dir("ovarian-10x"),
        ["meta", "core", "he"],
        downloader=lambda *a: pytest.fail("download"),
        bundle_fetcher=lambda *a: pytest.fail("download"),
    )
    assert all(c.status == "ok" for c in checks)
    assert sorted(p.name for p in raw_dir("ovarian-10x").rglob("*")) == before


def test_contract_ovarian_from_raw() -> None:
    from atlas_pipeline.adapters import get_adapter
    from atlas_pipeline.rawio import RawFileLog

    log = RawFileLog()
    cfg = load_config("ovarian-10x")
    ds = get_adapter("ovarian-10x")(cfg, log)
    rep = require_valid(ds, cfg)
    assert rep.ok and len(ds.cells) == 407124 and float(np.median(ds.cells.n_transcripts)) == 178
    assert len(ds.clusters) == 18 and len(ds.genes) == 5101
    assert log.forbidden_opened() == []
    assert ds.dataset.provenance["umap"]["source"] in ("provided", "recomputed")
    assert list(derived_dir("ovarian-10x").glob("umap-*.parquet")), "UMAP recompute cached under $DATA_ROOT/derived"


@pytest.mark.parametrize("name", ["synthetic-tma", "scale"])
def test_contract_synthetic(name: str) -> None:
    if not (canonical_dir(name) / "dataset.json").exists():
        pytest.skip(f"{name} canonical not built")
    ds = load_canonical(canonical_dir(name))
    assert require_valid(ds, load_config(name)).ok


def test_scale_size_budget() -> None:
    man = json.loads((current("scale") / "manifest.json").read_text())
    total = sum(s["bytes"] for s in man["sizes"].values())
    assert total <= 5e9


def test_alignment_raw_and_pyramid() -> None:
    rel = current("ovarian-10x")
    ds = load_canonical(canonical_dir("ovarian-10x"))
    sec = ds.sections.iloc[0]
    src = SourceImage(raw_dir("ovarian-10x") / sec.he_image)
    m = np.asarray(sec.affine, float).reshape(3, 3)
    xy = ds.cells[["x_um", "y_um"]].to_numpy()
    rng = np.random.default_rng(123)
    rand = align.tissue_points(src, m, float(sec.he_pixel_size_um), (0, 0, xy[:, 0].max(), xy[:, 1].max()), 1000, rng)
    sample, _ = align.raw_sampler(src, m, float(sec.he_pixel_size_um))
    r1 = align.run("T-PIPE-ALIGN-01", sample, xy, rand, np.random.default_rng(7))
    pdir = rel / "he/S1/S1-region"
    rd = TileReader(pdir, json.loads((pdir / "pyramid.json").read_text()))
    r = max(1, round(align.DISK_UM / rd.px))
    d = align.disk(r)
    r2 = align.run(
        "T-PIPE-ALIGN-02",
        lambda x, y: float(align.hematoxylin(rd.patch(x, y, r))[d].mean()),
        xy,
        rand,
        np.random.default_rng(7),
    )
    print("\n" + r1.render() + "\n" + r2.render())
    assert r1.passed and r2.passed
    he = json.loads((rel / "sections.json").read_text())[0]["he"]
    assert np.allclose(np.asarray(he["affine_source"]).ravel(), np.asarray(sec.affine_source))
    assert he["source_pixel_size_um"] == pytest.approx(0.274, abs=1e-3)


def test_quant_round_trip_ovarian() -> None:
    rel = current("ovarian-10x")
    ds = load_canonical(canonical_dir("ovarian-10x"))
    s = json.loads((rel / "sections.json").read_text())[0]
    q = assets.Quant(s["xy_offset"], s["xy_scale"])
    order = assets.cell_order(ds, {"S1": q})
    xy = np.frombuffer((rel / "cells/xy.u16").read_bytes(), "<u2").reshape(-1, 2)
    err = max(
        np.abs(q.decode(xy[:, 0]) - ds.cells.x_um.to_numpy()[order]).max(),
        np.abs(q.decode(xy[:, 1]) - ds.cells.y_um.to_numpy()[order]).max(),
    )
    man = json.loads((rel / "manifest.json").read_text())
    f = man["files"]["cells/umap.u16"]
    uq = np.frombuffer((rel / "cells/umap.u16").read_bytes(), "<u2").reshape(-1, 2)
    ux = ds.cells.umap_x.to_numpy(np.float64)[order]
    uerr = np.abs(f["offset"][0] + uq[:, 0] * f["scale"][0] - ux).max() / np.ptp(ux)
    print(f"\nT-PIPE-QUANT-01 ovarian-10x: max spatial error {err:.4f} µm, UMAP {uerr:.2e} of range")
    assert err <= 0.5 and uerr <= 0.001
