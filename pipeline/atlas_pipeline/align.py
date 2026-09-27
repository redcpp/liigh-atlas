"""Alignment tests T-PIPE-ALIGN-01 (raw H&E) and T-PIPE-ALIGN-02 (pre-aligned pyramid).

Hematoxylin (colour deconvolution, Ruifrok & Johnston via scikit-image ``rgb2hed``) is averaged over
a 1.5 µm disk at 1,000 random cell centroids and at 1,000 random in-tissue points (tissue: ~10 µm/px
block-averaged gray < 220, the brightfield background level). A correct µm → H&E transform puts
centroids on nuclei, so their hematoxylin is higher. Pass criteria, fixed before the first run:
one-sided Mann-Whitney p < 1e-6 and Cohen's d ≥ 0.8 (large). A negative control shifts the
centroids by 25 µm; its effect must stay below half the real one.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy.stats import mannwhitneyu
from skimage.color import rgb2hed

from .he import SourceImage

N_POINTS = 1000
DISK_UM = 1.5
P_MAX = 1e-6
D_MIN = 0.8
SHIFT_UM = 25.0
MASK_UM = 10.0
BACKGROUND_GRAY = 220

Sampler = Callable[[float, float], float]


@dataclass
class AlignResult:
    name: str
    n_cells: int
    n_random: int
    mean_cells: float
    mean_random: float
    cohens_d: float
    rank_biserial: float
    p_value: float
    control_d: float

    @property
    def passed(self) -> bool:
        return self.p_value < P_MAX and self.cohens_d >= D_MIN and self.control_d < self.cohens_d / 2

    def render(self) -> str:
        return (
            f"{self.name}: hematoxylin OD at cell centroids {self.mean_cells:.4f} vs random in-tissue "
            f"{self.mean_random:.4f} (n={self.n_cells}/{self.n_random}); Cohen's d = {self.cohens_d:.3f}, "
            f"rank-biserial = {self.rank_biserial:.3f}, one-sided Mann-Whitney p = {self.p_value:.3e}; "
            f"negative control (centroids shifted {SHIFT_UM:g} µm) d = {self.control_d:.3f}; "
            f"criteria p < {P_MAX:g}, d ≥ {D_MIN:g} -> {'PASS' if self.passed else 'FAIL'}"
        )


def hematoxylin(rgb: NDArray[Any]) -> NDArray[Any]:
    return np.asarray(rgb2hed(rgb)[..., 0], dtype=np.float64)


def disk(r: int) -> NDArray[Any]:
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    return np.asarray(xx**2 + yy**2 <= r * r)


def tissue_mask(src: SourceImage, src_px_um: float) -> tuple[NDArray[Any], float, float]:
    """Tissue mask at ≈ MASK_UM per pixel: block-averaged gray below the brightfield background level.

    A fixed background threshold (not Otsu) so a crop with no background is all tissue instead of being
    split into nuclei vs stroma. Returns the mask and its pixel size in level-0 H&E px (x, y).
    """
    k = 0
    for i, (fx, fy) in enumerate(src.factors):
        if src_px_um * max(fx, fy) <= MASK_UM:
            k = i
    h, w = src.shapes[k]
    img = src.read(k, 0, 0, w, h)
    fx, fy = src.factors[k]
    shrink = max(1.0, MASK_UM / (src_px_um * max(fx, fy)))
    nw, nh = max(1, round(w / shrink)), max(1, round(h / shrink))
    small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    gray = small.mean(axis=2)
    return np.asarray(gray < BACKGROUND_GRAY), fx * w / nw, fy * h / nh


def tissue_points(
    src: SourceImage,
    um_to_px: NDArray[Any],
    src_px_um: float,
    bounds: tuple[float, float, float, float],
    n: int,
    rng: np.random.Generator,
) -> NDArray[Any]:
    """``n`` uniform µm points inside ``bounds`` whose H&E position is tissue."""
    mask, sx, sy = tissue_mask(src, src_px_um)
    h, w = mask.shape
    out: list[NDArray[Any]] = []
    got = 0
    x0, y0, x1, y1 = bounds
    for _ in range(1000):
        pts = np.column_stack([rng.uniform(x0, x1, 4 * n), rng.uniform(y0, y1, 4 * n)])
        px = to_px(um_to_px, pts)
        u = np.floor((px[:, 0] + 0.5) / sx).astype(int)
        v = np.floor((px[:, 1] + 0.5) / sy).astype(int)
        ok = (u >= 0) & (u < w) & (v >= 0) & (v < h)
        ok[ok] = mask[v[ok], u[ok]]
        out.append(pts[ok])
        got += int(ok.sum())
        if got >= n:
            break
    return np.asarray(np.concatenate(out)[:n])


def to_px(m: NDArray[Any], pts: NDArray[Any]) -> NDArray[Any]:
    hom = np.column_stack([pts, np.ones(len(pts))])
    return np.asarray((m @ hom.T).T[:, :2])


def raw_sampler(src: SourceImage, um_to_px: NDArray[Any], src_px_um: float) -> tuple[Sampler, int]:
    r = max(1, round(DISK_UM / src_px_um))
    d = disk(r)

    def sample(x: float, y: float) -> float:
        u, v = to_px(um_to_px, np.array([[x, y]]))[0]
        cu, cv = int(round(u)), int(round(v))
        patch = src.read(0, cu - r, cv - r, cu + r + 1, cv + r + 1)
        return float(hematoxylin(patch)[d].mean())

    return sample, r


def run(
    name: str, sample: Sampler, cells_xy: NDArray[Any], random_xy: NDArray[Any], rng: np.random.Generator
) -> AlignResult:
    idx = rng.choice(len(cells_xy), size=min(N_POINTS, len(cells_xy)), replace=False)
    pts = cells_xy[idx]
    a = np.array([sample(x, y) for x, y in pts])
    b = np.array([sample(x, y) for x, y in random_xy])
    ang = rng.uniform(0, 2 * math.pi, len(pts))
    shifted = pts + SHIFT_UM * np.column_stack([np.cos(ang), np.sin(ang)])
    c = np.array([sample(x, y) for x, y in shifted])
    u = mannwhitneyu(a, b, alternative="greater")
    return AlignResult(
        name=name,
        n_cells=len(a),
        n_random=len(b),
        mean_cells=float(a.mean()),
        mean_random=float(b.mean()),
        cohens_d=cohens_d(a, b),
        rank_biserial=float(2 * u.statistic / (len(a) * len(b)) - 1),
        p_value=float(u.pvalue),
        control_d=cohens_d(c, b),
    )


def cohens_d(a: NDArray[Any], b: NDArray[Any]) -> float:
    pooled = math.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / pooled) if pooled > 0 else 0.0
