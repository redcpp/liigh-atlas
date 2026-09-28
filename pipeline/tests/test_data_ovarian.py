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
    """Both tissue definitions: centroids pass the rule, the 25 µm-shifted control fails (Gate 1)."""
    rel = current("ovarian-10x")
    ds = load_canonical(canonical_dir("ovarian-10x"))
    sec = ds.sections.iloc[0]
    src = SourceImage(raw_dir("ovarian-10x") / sec.he_image)
    m = np.asarray(sec.affine, float).reshape(3, 3)
    xy = ds.cells[["x_um", "y_um"]].to_numpy()
    rand = align.random_points(src, m, float(sec.he_pixel_size_um), xy, np.random.default_rng(123))
    sample, _ = align.raw_sampler(src, m, float(sec.he_pixel_size_um))
    r1 = align.run_suite("T-PIPE-ALIGN-01", sample, xy, rand, np.random.default_rng(7))
    pdir = rel / "he/S1/S1-region"
    rd = TileReader(pdir, json.loads((pdir / "pyramid.json").read_text()))
    r = max(1, round(align.DISK_UM / rd.px))
    d = align.disk(r)
    r2 = align.run_suite(
        "T-PIPE-ALIGN-02",
        lambda x, y: float(align.hematoxylin(rd.patch(x, y, r))[d].mean()),
        xy,
        rand,
        np.random.default_rng(7),
    )
    print("\n" + r1.render() + "\n" + r2.render())
    for suite in (r1, r2):
        assert suite.passed
        assert len(suite.comparisons) == 4
        assert all(c.passed == (c.group == "centroids") for c in suite.comparisons)
    he = json.loads((rel / "sections.json").read_text())[0]["he"]
    assert np.allclose(np.asarray(he["affine_source"]).ravel(), np.asarray(sec.affine_source))
    assert he["source_pixel_size_um"] == pytest.approx(0.274, abs=1e-3)


def oracle_skip_reason(outs: Path) -> str | None:
    """Gate 1: cells.zarr.zip is a test-only input; without it the oracle skips (never fails)."""
    zz = outs / "cells.zarr.zip"
    if not zz.exists():
        return (
            f"T-PIPE-ORACLE-01 skipped: test-only input {zz} is absent "
            "(spatialdata-io 0.7.1 needs cells.zarr.zip to build the cells table; the pipeline never reads it)"
        )
    return None


def test_spatialdata_io_oracle() -> None:
    """ADR-0009 (b): spatialdata-io (test-only; transcripts, images, labels, boundaries off) agrees with our
    reader on cell ids, centroids and matrix shape. spatialdata-io 0.7.1 needs cells.zarr.zip for the
    table, so the oracle (never the pipeline) reads it; it must open no transcripts.* or morphology* file."""
    sdio = pytest.importorskip("spatialdata_io")
    reason = oracle_skip_reason(raw_dir("ovarian-10x") / "outs")
    if reason:
        pytest.skip(reason)
    import sys

    from atlas_pipeline.adapters import get_adapter
    from atlas_pipeline.rawio import RawFileLog

    opened: list[str] = []
    recording = [True]

    def hook(event: str, args: tuple[object, ...]) -> None:
        if recording[0] and event == "open" and isinstance(args[0], str) and "/raw/" in args[0]:
            opened.append(args[0])

    sys.addaudithook(hook)
    try:
        sd = sdio.xenium(
            raw_dir("ovarian-10x") / "outs",
            cells_boundaries=False,
            nucleus_boundaries=False,
            cells_as_circles=False,
            cells_labels=False,
            nucleus_labels=False,
            transcripts=False,
            morphology_mip=False,
            morphology_focus=False,
            aligned_images=False,
            cells_table=True,
            gex_only=True,
        )
    finally:
        recording[0] = False
    names = {Path(p).name for p in opened}
    print(f"\noracle opened: {sorted(names)}")
    assert not any(n.startswith(("transcripts", "morphology")) for n in names)
    table = sd.tables["table"]
    ours = get_adapter("ovarian-10x")(load_config("ovarian-10x"), RawFileLog())
    assert table.obs.cell_id.astype(str).tolist() == ours.cells.cell_id.tolist()
    err = np.abs(np.asarray(table.obsm["spatial"], np.float64) - ours.cells[["x_um", "y_um"]].to_numpy()).max()
    assert err < 1e-3, err  # the oracle stores float32 centroids
    assert table.shape == ours.expression.shape == (407124, 5101)
    assert table.var.gene_ids.tolist() == ours.genes.gene_id.tolist()
    print(f"oracle: {table.shape[0]} cell ids identical, max centroid |Δ| = {err:.2e} µm, shape {table.shape}")


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
    has = ds.cells.has_umap.to_numpy(bool)[order]
    assert ((uq[:, 0] == f["missing"]) == ~has).all()
    assert man["counts"]["cells_without_umap"] == 513
    ux = ds.cells.umap_x.to_numpy(np.float64)[order][has]
    uerr = np.abs(f["offset"][0] + uq[has, 0] * f["scale"][0] - ux).max() / np.ptp(ux)
    print(f"\nT-PIPE-QUANT-01 ovarian-10x: max spatial error {err:.4f} µm, UMAP {uerr:.2e} of range")
    assert err <= 0.5 and uerr <= 0.001
