"""Alignment tests T-PIPE-ALIGN-01 (raw H&E) and T-PIPE-ALIGN-02 (pre-aligned pyramid).

Hematoxylin (colour deconvolution, Ruifrok & Johnston via scikit-image ``rgb2hed``) is averaged over
a 1.5 µm disk at 1,000 random cell centroids and at 1,000 random in-tissue points. A correct
µm → H&E transform puts centroids on nuclei, so their hematoxylin is higher.

Two tissue definitions (Gate 1): (1) brightfield mask, ~10 µm/px block-averaged gray < 220; (2) an
image-independent one, random points within 20 µm of any cell centroid. Pass rule, fixed before the
first run: one-sided Mann-Whitney p < 1e-6 and Cohen's d ≥ 0.8 (large), under both definitions. The
negative control (the same centroids shifted 25 µm in a random direction) must fail the rule under both.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree
from scipy.stats import mannwhitneyu
from skimage.color import rgb2hed

from .he import SourceImage

N_POINTS = 1000
DISK_UM = 1.5
P_MAX = 1e-6
D_MIN = 0.8
SHIFT_UM = 25.0
MASK_UM = 10.0
NEAR_CELL_UM = 20.0
MASK_BRIGHTFIELD = "brightfield mask"
MASK_NEAR_CELL = "≤ 20 µm from a cell"
BACKGROUND_GRAY = 220

Sampler = Callable[[float, float], float]


@dataclass
class Comparison:
    """One two-sample comparison: hematoxylin at ``group`` points vs random in-tissue points."""

    mask: str
    group: str  # "centroids" | "shifted 25 µm (control)"
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    cohens_d: float
    rank_biserial: float
    p_value: float

    @property
    def passed(self) -> bool:
        return self.p_value < P_MAX and self.cohens_d >= D_MIN

    def render(self) -> str:
        return (
            f"  [{self.mask}] {self.group}: hematoxylin OD {self.mean_a:.4f} vs random in-tissue {self.mean_b:.4f} "
            f"(n={self.n_a}/{self.n_b}); Cohen's d = {self.cohens_d:.3f}, rank-biserial = {self.rank_biserial:.3f}, "
            f"one-sided Mann-Whitney p = {self.p_value:.3e} -> {'passes' if self.passed else 'fails'} the rule"
        )


@dataclass
class AlignSuite:
    name: str
    comparisons: list[Comparison]

    @property
    def passed(self) -> bool:
        real = [c for c in self.comparisons if c.group == "centroids"]
        ctrl = [c for c in self.comparisons if c.group != "centroids"]
        return bool(real) and bool(ctrl) and all(c.passed for c in real) and not any(c.passed for c in ctrl)

    def render(self) -> str:
        lines = [f"{self.name} (rule: p < {P_MAX:g} and d ≥ {D_MIN:g}; centroids must pass, control must fail)"]
        lines += [c.render() for c in self.comparisons]
        lines.append(f"  -> {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


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


def near_cell_points(
    cells_xy: NDArray[Any], bounds: tuple[float, float, float, float], n: int, rng: np.random.Generator
) -> NDArray[Any]:
    """``n`` uniform µm points inside ``bounds`` within NEAR_CELL_UM of a cell centroid (no image used)."""
    tree = cKDTree(cells_xy)
    x0, y0, x1, y1 = bounds
    out: list[NDArray[Any]] = []
    got = 0
    for _ in range(1000):
        pts = np.column_stack([rng.uniform(x0, x1, 4 * n), rng.uniform(y0, y1, 4 * n)])
        dist, _ = tree.query(pts, distance_upper_bound=NEAR_CELL_UM)
        ok = np.isfinite(dist)
        out.append(pts[ok])
        got += int(ok.sum())
        if got >= n:
            break
    return np.asarray(np.concatenate(out)[:n])


def compare(mask: str, group: str, a: NDArray[Any], b: NDArray[Any]) -> Comparison:
    u = mannwhitneyu(a, b, alternative="greater")
    return Comparison(
        mask=mask,
        group=group,
        n_a=len(a),
        n_b=len(b),
        mean_a=float(a.mean()),
        mean_b=float(b.mean()),
        cohens_d=cohens_d(a, b),
        rank_biserial=float(2 * u.statistic / (len(a) * len(b)) - 1),
        p_value=float(u.pvalue),
    )


def run_suite(
    name: str,
    sample: Sampler,
    cells_xy: NDArray[Any],
    random_by_mask: dict[str, NDArray[Any]],
    rng: np.random.Generator,
) -> AlignSuite:
    idx = rng.choice(len(cells_xy), size=min(N_POINTS, len(cells_xy)), replace=False)
    pts = cells_xy[idx]
    ang = rng.uniform(0, 2 * math.pi, len(pts))
    shifted = pts + SHIFT_UM * np.column_stack([np.cos(ang), np.sin(ang)])
    a = np.array([sample(x, y) for x, y in pts])
    c = np.array([sample(x, y) for x, y in shifted])
    comps = []
    for mask, rand in random_by_mask.items():
        b = np.array([sample(x, y) for x, y in rand])
        comps.append(compare(mask, "centroids", a, b))
        comps.append(compare(mask, f"shifted {SHIFT_UM:g} µm (control)", c, b))
    return AlignSuite(name, comps)


def random_points(
    src: SourceImage,
    um_to_px: NDArray[Any],
    src_px_um: float,
    cells_xy: NDArray[Any],
    rng: np.random.Generator,
) -> dict[str, NDArray[Any]]:
    bounds = (
        float(cells_xy[:, 0].min()),
        float(cells_xy[:, 1].min()),
        float(cells_xy[:, 0].max()),
        float(cells_xy[:, 1].max()),
    )
    return {
        MASK_BRIGHTFIELD: tissue_points(src, um_to_px, src_px_um, bounds, N_POINTS, rng),
        MASK_NEAR_CELL: near_cell_points(cells_xy, bounds, N_POINTS, rng),
    }


def cohens_d(a: NDArray[Any], b: NDArray[Any]) -> float:
    pooled = math.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / pooled) if pooled > 0 else 0.0
