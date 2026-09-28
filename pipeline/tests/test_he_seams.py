"""T-PIPE-HE-02 (ADR-0009 c): warping in blocks gives the same pixels as one single-pass warp.

Tolerance fixed before the first run: max abs difference ≤ 2 levels (of 255) per channel.
Covers the Lanczos path (output ≈ source pixel) and the box-shrink path (output ≈ 2 source pixels).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from atlas_pipeline.adapters.common import he_affine
from atlas_pipeline.adapters.fixture import FIXTURE_DIR
from atlas_pipeline.he import KERNEL_MARGIN, SourceImage, render

MAX_DIFF = 2
BLOCK = 256


@pytest.mark.parametrize("px_um", [0.27, 0.54])
def test_tiled_warp_matches_single_pass(px_um: float) -> None:
    sec = json.loads((FIXTURE_DIR / "sections.json").read_text())[0]
    m = he_affine(np.asarray(sec["affine_source"], float).reshape(3, 3), sec["pixel_size"])
    src = SourceImage(FIXTURE_DIR / sec["he_image"])
    x0, y0, w, h = 40.0, 60.0, 3 * BLOCK + 37, 2 * BLOCK + 11  # blocks that do not divide evenly
    single = render(src, m, x0, y0, px_um, w, h, sec["he_pixel_size_um"])
    tiled = np.zeros_like(single)
    for by in range(0, h, BLOCK):
        for bx in range(0, w, BLOCK):
            bw, bh = min(BLOCK, w - bx), min(BLOCK, h - by)
            tiled[by : by + bh, bx : bx + bw] = render(
                src, m, x0 + bx * px_um, y0 + by * px_um, px_um, bw, bh, sec["he_pixel_size_um"]
            )
    diff = np.abs(single.astype(int) - tiled.astype(int))
    print(f"\nT-PIPE-HE-02 px={px_um} µm: max |tiled − single| = {diff.max()}, mean = {diff.mean():.4f}")
    assert diff.max() <= MAX_DIFF
    assert KERNEL_MARGIN >= 8


def test_warp_refuses_oversized_calls() -> None:
    sec = json.loads((FIXTURE_DIR / "sections.json").read_text())[0]
    m = he_affine(np.asarray(sec["affine_source"], float).reshape(3, 3), sec["pixel_size"])
    src = SourceImage(FIXTURE_DIR / sec["he_image"])
    with pytest.raises(ValueError, match="OpenCV"):
        render(src, m, 0.0, 0.0, 0.27, 32767, 4, sec["he_pixel_size_um"])
