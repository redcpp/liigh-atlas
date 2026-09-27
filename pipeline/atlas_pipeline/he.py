"""H&E pyramid (ADR-0004): warp once into the section µm frame with Lanczos, 512 px WebP tiles per core.

Convention: affines map continuous coordinates where integer values are pixel centres (OpenCV style).
Output level ``z`` (0 = coarsest, ``nz-1`` = full resolution) has pixel size ``px · 2^(nz-1-z)``.
"""

from __future__ import annotations

import io
import math
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import tifffile
import zarr
from numpy.typing import NDArray
from PIL import Image

TILE = 512
BLOCK_TILES = 4
WEBP_QUALITY = 85
WEBP_METHOD = 4
THUMB = 256
MARGIN_UM = 50.0
KERNEL_MARGIN = 6  # Lanczos4 needs 4 px on each side; keep a little extra


@dataclass
class SourceImage:
    """Pyramidal OME-TIFF opened lazily; one TiffFile per thread (tifffile handles are not shared)."""

    path: Path

    def __post_init__(self) -> None:
        self._local = threading.local()
        with tifffile.TiffFile(self.path) as tif:
            self.shapes = [tuple(int(s) for s in lvl.shape[:2]) for lvl in tif.series[0].levels]
        h0, w0 = self.shapes[0]
        self.factors = [(w0 / w, h0 / h) for h, w in self.shapes]

    def level(self, k: int) -> Any:
        if not hasattr(self._local, "arrays"):
            tif = tifffile.TiffFile(self.path)
            store = tif.series[0].aszarr()
            z = zarr.open(store, mode="r")
            arrays = [z] if isinstance(z, zarr.Array) else [z[str(i)] for i in range(len(self.shapes))]
            self._local.tif, self._local.arrays = tif, arrays
        return self._local.arrays[k]

    def read(self, k: int, x0: int, y0: int, x1: int, y1: int) -> NDArray[Any]:
        """Window [y0:y1, x0:x1] of level k, padded with white where it leaves the image."""
        h, w = self.shapes[k]
        out = np.full((y1 - y0, x1 - x0, 3), 255, np.uint8)
        cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
        if cx1 > cx0 and cy1 > cy0:
            out[cy0 - y0 : cy1 - y0, cx0 - x0 : cx1 - x0] = np.asarray(self.level(k)[cy0:cy1, cx0:cx1])[..., :3]
        return out


def render(
    src: SourceImage,
    um_to_px: NDArray[Any],
    x0_um: float,
    y0_um: float,
    px_um: float,
    width: int,
    height: int,
    src_px_um: float,
) -> NDArray[Any]:
    """Resample the µm-frame rectangle (x0, y0, width × height px of size px_um) from the source."""
    # pick the coarsest source level whose pixel is at most 5% larger than the output pixel
    k = 0
    for i, (fx, fy) in enumerate(src.factors):
        if src_px_um * max(fx, fy) <= px_um * 1.05:
            k = i
    fx, fy = src.factors[k]
    # dst index -> µm -> level-0 px -> level-k px
    d2um = np.array([[px_um, 0, x0_um + 0.5 * px_um], [0, px_um, y0_um + 0.5 * px_um], [0, 0, 1]])
    l0_to_lk = np.array([[1 / fx, 0, 0.5 / fx - 0.5], [0, 1 / fy, 0.5 / fy - 0.5], [0, 0, 1]])
    m = l0_to_lk @ um_to_px @ d2um
    corners = np.array(
        [[-0.5, -0.5, 1], [width - 0.5, -0.5, 1], [-0.5, height - 0.5, 1], [width - 0.5, height - 0.5, 1]]
    )
    sc = (m @ corners.T)[:2]
    wx0, wy0 = int(math.floor(sc[0].min())) - KERNEL_MARGIN, int(math.floor(sc[1].min())) - KERNEL_MARGIN
    wx1, wy1 = int(math.ceil(sc[0].max())) + KERNEL_MARGIN, int(math.ceil(sc[1].max())) + KERNEL_MARGIN
    win = src.read(k, wx0, wy0, wx1, wy1)
    m = np.array([[1, 0, -wx0], [0, 1, -wy0], [0, 0, 1]]) @ m
    ratio = math.sqrt(abs(np.linalg.det(m[:2, :2])))  # source px per output px
    if ratio > 1.25:  # anti-alias before the Lanczos warp
        nw, nh = max(1, round(win.shape[1] / ratio)), max(1, round(win.shape[0] / ratio))
        sx, sy = nw / win.shape[1], nh / win.shape[0]
        win = cv2.resize(win, (nw, nh), interpolation=cv2.INTER_AREA)
        m = np.array([[sx, 0, 0.5 * sx - 0.5], [0, sy, 0.5 * sy - 0.5], [0, 0, 1]]) @ m
    out = cv2.warpAffine(
        win,
        m[:2].astype(np.float64),
        (width, height),
        flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return np.asarray(out, dtype=np.uint8)


def webp(img: NDArray[Any]) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    return buf.getvalue()


@dataclass(frozen=True)
class Pyramid:
    x0_um: float
    y0_um: float
    width_um: float
    height_um: float
    px_um: float  # full-resolution output pixel size
    nz: int

    @staticmethod
    def fit(bbox: tuple[float, float, float, float], src_px_um: float) -> Pyramid:
        x0, y0, x1, y1 = bbox[0] - MARGIN_UM, bbox[1] - MARGIN_UM, bbox[2] + MARGIN_UM, bbox[3] + MARGIN_UM
        px = math.floor(src_px_um * 100) / 100  # ≤ source pixel size (Gate 0)
        w0 = math.ceil((x1 - x0) / px)
        h0 = math.ceil((y1 - y0) / px)
        nz = max(1, math.ceil(math.log2(max(w0, h0) / TILE)) + 1)
        return Pyramid(x0, y0, x1 - x0, y1 - y0, px, nz)

    def level_px(self, z: int) -> float:
        return float(self.px_um * 2 ** (self.nz - 1 - z))

    def level_size(self, z: int) -> tuple[int, int]:
        p = self.level_px(z)
        return math.ceil(self.width_um / p), math.ceil(self.height_um / p)

    def meta(self) -> dict[str, Any]:
        levels = []
        for z in range(self.nz):
            w, h = self.level_size(z)
            levels.append(
                {
                    "z": z,
                    "px_um": self.level_px(z),
                    "width": w,
                    "height": h,
                    "cols": math.ceil(w / TILE),
                    "rows": math.ceil(h / TILE),
                }
            )
        return {
            "origin_um": [self.x0_um, self.y0_um],
            "size_um": [self.width_um, self.height_um],
            "tile": TILE,
            "format": "webp",
            "quality": WEBP_QUALITY,
            "resampling": "lanczos4",
            "levels": levels,
        }


def blocks(pyr: Pyramid, z: int) -> Iterator[tuple[int, int, int, int]]:
    w, h = pyr.level_size(z)
    step = TILE * BLOCK_TILES
    for by in range(0, h, step):
        for bx in range(0, w, step):
            yield bx, by, min(step, w - bx), min(step, h - by)


def build_pyramid(
    src: SourceImage,
    um_to_px: NDArray[Any],
    src_px_um: float,
    pyr: Pyramid,
    prefix: str,
    emit: Callable[[str, bytes], None],
    workers: int = 8,
) -> None:
    """Render every tile of ``pyr``; ``emit(relpath, bytes)`` is called in deterministic order."""
    for z in range(pyr.nz):
        p = pyr.level_px(z)

        def job(b: tuple[int, int, int, int], p: float = p) -> list[tuple[int, int, bytes]]:
            bx, by, bw, bh = b
            img = render(src, um_to_px, pyr.x0_um + bx * p, pyr.y0_um + by * p, p, bw, bh, src_px_um)
            out = []
            for ty in range(0, bh, TILE):
                for tx in range(0, bw, TILE):
                    out.append(((bx + tx) // TILE, (by + ty) // TILE, webp(img[ty : ty + TILE, tx : tx + TILE])))
            return out

        with ThreadPoolExecutor(workers) as ex:
            results = list(ex.map(job, list(blocks(pyr, z))))
        for tiles in results:
            for tx, ty, data in tiles:
                emit(f"{prefix}/{z}/{tx}_{ty}.webp", data)


def thumbnail(src: SourceImage, um_to_px: NDArray[Any], src_px_um: float, pyr: Pyramid) -> bytes:
    p = max(pyr.width_um, pyr.height_um) / THUMB
    w, h = max(1, round(pyr.width_um / p)), max(1, round(pyr.height_um / p))
    return webp(render(src, um_to_px, pyr.x0_um, pyr.y0_um, p, w, h, src_px_um))


class TileReader:
    """Reads the full-resolution level of a built pyramid (for T-PIPE-ALIGN-02)."""

    def __init__(self, root: Path, meta: dict[str, Any]) -> None:
        self.root, self.meta = root, meta
        self.z = len(meta["levels"]) - 1
        self.px = float(meta["levels"][-1]["px_um"])
        self.x0, self.y0 = (float(v) for v in meta["origin_um"])
        self._cache: dict[tuple[int, int], NDArray[Any]] = {}

    def tile(self, tx: int, ty: int) -> NDArray[Any]:
        key = (tx, ty)
        if key not in self._cache:
            with Image.open(self.root / f"{self.z}/{tx}_{ty}.webp") as im:
                self._cache[key] = np.asarray(im.convert("RGB"))
        return self._cache[key]

    def patch(self, x_um: float, y_um: float, r: int) -> NDArray[Any]:
        cx = int(round((x_um - self.x0) / self.px - 0.5))
        cy = int(round((y_um - self.y0) / self.px - 0.5))
        lvl = self.meta["levels"][-1]
        out = np.full((2 * r + 1, 2 * r + 1, 3), 255, np.uint8)
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if 0 <= xx < lvl["width"] and 0 <= yy < lvl["height"]:
                    t = self.tile(xx // TILE, yy // TILE)
                    out[yy - cy + r, xx - cx + r] = t[yy % TILE, xx % TILE]
        return out
