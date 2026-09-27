"""End-to-end on the committed fixture: T-PIPE-CORES-01, T-PIPE-HE-01, T-PIPE-ALIGN-01/02 (fixture),
T-PIPE-QUANT-01, T-PIPE-REPRO-01 (fixture), manifest layout (ADR-0002)."""

from __future__ import annotations

import json

import numpy as np
from PIL import Image

from atlas_pipeline import assets, he
from atlas_pipeline.canonical_io import load as load_canonical
from atlas_pipeline.config import load_config
from atlas_pipeline.run import out_root, repro


def test_summary_and_manifest(fixture_run) -> None:
    s = fixture_run
    man = json.loads((s.out_dir / "manifest.json").read_text())
    assert s.out_dir.name == s.release and len(s.release) == 12
    assert man["counts"] == {
        "cells": 2821,
        "genes": 150,
        "clusters": 14,
        "cores": 4,
        "sections": 1,
        "patients": 3,
    }
    assert man["dataset"]["synthetic"] is True and "release" not in man["dataset"]
    assert set(man["indexes"]) == {"expression", "he"}
    for rel, info in man["files"].items():
        assert (s.out_dir / rel).stat().st_size == info["bytes"]
    text = s.render()
    assert "cells = 2821" in text and "TOTAL" in text and "PASS" in text


def test_cores_contiguous_and_ordered(fixture_run) -> None:
    cores = json.loads((fixture_run.out_dir / "cores.json").read_text())
    core_idx = np.frombuffer((fixture_run.out_dir / "cells/core.u16").read_bytes(), "<u2")
    ends = 0
    for i, c in enumerate(cores):
        a, b = c["cell_range"]
        assert a == ends and np.all(core_idx[a:b] == i)
        ends = b
    assert ends == len(core_idx)


def test_quantization_round_trip_against_canonical(fixture_run) -> None:
    ds = load_canonical(out_root(load_config("fixture")) / "canonical")
    secs = json.loads((fixture_run.out_dir / "sections.json").read_text())
    q = assets.Quant(secs[0]["xy_offset"], secs[0]["xy_scale"])
    order = assets.cell_order(ds, {"S1": q})
    xy = np.frombuffer((fixture_run.out_dir / "cells/xy.u16").read_bytes(), "<u2").reshape(-1, 2)
    err = np.abs(q.decode(xy[:, 0]) - ds.cells.x_um.to_numpy()[order]).max()
    assert err <= 0.5 and fixture_run.quant_errors["xy_um[S1]"] <= 0.5


def test_expression_files_decode(fixture_run) -> None:
    genes = json.loads((fixture_run.out_dir / "genes.json").read_text())
    n = 2821
    for g in genes[:10]:
        v = assets.decode_gene((fixture_run.out_dir / g["file"]).read_bytes(), n)
        assert int((v > 0).sum()) == g["nnz"] and (g["max_v"] > 0) == (g["nnz"] > 0)


def test_he_pyramid_geometry(fixture_run) -> None:
    root = fixture_run.out_dir / "he/S1/C001"
    meta = json.loads((root / "pyramid.json").read_text())
    lv = meta["levels"]
    assert lv[-1]["px_um"] <= 0.2740 and meta["resampling"] == "lanczos4"
    assert lv[0]["cols"] == 1 and lv[0]["rows"] == 1
    for level in lv:
        for ty in range(level["rows"]):
            for tx in range(level["cols"]):
                with Image.open(root / f"{level['z']}/{tx}_{ty}.webp") as im:
                    w = min(he.TILE, level["width"] - tx * he.TILE)
                    h = min(he.TILE, level["height"] - ty * he.TILE)
                    assert im.size == (w, h)
    with Image.open(fixture_run.out_dir / "thumbs/C001.webp") as t:
        assert max(t.size) == he.THUMB
    secs = json.loads((fixture_run.out_dir / "sections.json").read_text())
    assert secs[0]["he"]["source_pixel_size_um"] > 0.27 and len(secs[0]["he"]["affine_source"]) == 3


def test_alignment_passes_on_fixture(fixture_run) -> None:
    names = [r.name for r in fixture_run.align]
    assert any("ALIGN-01" in n for n in names) and any("ALIGN-02" in n for n in names)
    for r in fixture_run.align:
        assert r.passed, r.render()
        assert r.n_cells == 1000 and r.n_random == 1000


def test_repro_fixture(fixture_run) -> None:
    ok, text = repro("fixture")
    assert ok, text
    assert "IDENTICAL" in text
