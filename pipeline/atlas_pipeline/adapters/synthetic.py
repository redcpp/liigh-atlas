"""`synthetic-tma` and `scale` adapters (BRIEF §4.3, TECH_SPEC §2), derived from the ovarian-10x canonical.

synthetic-tma: seeded Poisson-disk 1 mm cores with ≥ 80% tissue coverage, laid on a TMA grid over
3 synthetic sections, patients assigned with some having ≥ 2 cores. scale: replicates those cores
(new IDs, rotated + jittered) to ≥ 443K cells and ≥ 100 cores, 62 patients, and 23 clusters by
splitting the 5 largest 10x groups in two (seeded k-means on PCA). No invented biology in labels.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp
from numpy.typing import NDArray

from .. import PIPELINE_VERSION
from ..canonical_io import load as load_canonical
from ..config import DatasetConfig, load_config
from ..contract import CanonicalDataset, DatasetRecord
from ..env import canonical_dir
from ..rawio import RawFileLog
from .common import cluster_table

log = logging.getLogger(__name__)
ADAPTER_VERSION = "1"
GRID_PITCH_UM = 1500.0
SECTION_MARGIN_UM = 1000.0
COVERAGE_BIN_UM = 50.0
MIN_COVERAGE = 0.8
CORE_GAP_UM = 100.0


def load(cfg: DatasetConfig, rawlog: RawFileLog) -> CanonicalDataset:
    assert cfg.source is not None
    src_dir = canonical_dir(cfg.source)
    if not (src_dir / "dataset.json").exists():
        raise FileNotFoundError(f"{src_dir} missing: run `make pipeline DATASET={cfg.source}` first")
    for f in sorted(src_dir.iterdir()):
        rawlog.use(f, kind="canonical")
    src = load_canonical(src_dir)
    return derive(src, cfg)


def derive(src: CanonicalDataset, cfg: DatasetConfig) -> CanonicalDataset:
    rng = np.random.default_rng(cfg.seed)
    x, y = src.cells.x_um.to_numpy(), src.cells.y_um.to_numpy()
    centers = pick_cores(x, y, cfg.core_radius_um, rng)
    log.info(
        "cores cut from tissue: %d (radius %.0f µm, coverage ≥ %.0f%%)",
        len(centers),
        cfg.core_radius_um,
        MIN_COVERAGE * 100,
    )
    members = [np.flatnonzero(np.hypot(x - cx, y - cy) <= cfg.core_radius_um) for cx, cy in centers]

    # replicate for scale
    plan: list[tuple[int, int]] = [(i, 0) for i in range(len(centers))]  # (base core, replicate)
    if cfg.target_cells or cfg.min_cores:
        total, rep = sum(len(m) for m in members), 0
        while total < (cfg.target_cells or 0) or len(plan) < (cfg.min_cores or 0):
            rep += 1
            for i in range(len(centers)):
                plan.append((i, rep))
                total += len(members[i])
                if total >= (cfg.target_cells or 0) and len(plan) >= (cfg.min_cores or 0):
                    break
    n_cores = len(plan)
    n_sec = cfg.n_sections
    per_sec = math.ceil(n_cores / n_sec)
    cols = math.ceil(math.sqrt(per_sec))
    patients = assign_patients(n_cores, cfg.n_patients, rng)

    labels, colors, cell_cluster = clusters_for(src, cfg)

    rows: list[NDArray[Any]] = []
    core_recs, cell_parts = [], []
    for c, (base, rep) in enumerate(plan):
        sec = c % n_sec
        slot = c // n_sec
        gx, gy = slot % cols, slot // cols
        ncx = SECTION_MARGIN_UM + (gx + 0.5) * GRID_PITCH_UM
        ncy = SECTION_MARGIN_UM + (gy + 0.5) * GRID_PITCH_UM
        idx = members[base]
        dx, dy = x[idx] - centers[base][0], y[idx] - centers[base][1]
        if rep:
            th = rng.uniform(0, 2 * math.pi)
            dx, dy = dx * math.cos(th) - dy * math.sin(th), dx * math.sin(th) + dy * math.cos(th)
            dx = dx + rng.normal(0, 0.5, len(idx))
            dy = dy + rng.normal(0, 0.5, len(idx))
            scale_r = cfg.core_radius_um / max(np.hypot(dx, dy).max(), cfg.core_radius_um)
            dx, dy = dx * scale_r, dy * scale_r
        core_id, sid, pid = f"C{c + 1:03d}", f"S{sec + 1}", patients[c]
        cx_, cy_ = ncx + dx, ncy + dy
        core_recs.append(
            {
                "core_id": core_id,
                "section_id": sid,
                "patient_id": pid,
                "kind": "core",
                "center_x_um": ncx,
                "center_y_um": ncy,
                "radius_um": cfg.core_radius_um,
                "bbox_x0": float(min(cx_.min(), ncx - cfg.core_radius_um)),
                "bbox_y0": float(min(cy_.min(), ncy - cfg.core_radius_um)),
                "bbox_x1": float(max(cx_.max(), ncx + cfg.core_radius_um)),
                "bbox_y1": float(max(cy_.max(), ncy + cfg.core_radius_um)),
            }
        )
        suffix = "" if rep == 0 else f"-r{rep}"
        cell_parts.append(
            pd.DataFrame(
                {
                    "cell_id": src.cells.cell_id.to_numpy()[idx] + suffix,
                    "section_id": sid,
                    "core_id": core_id,
                    "patient_id": pid,
                    "x_um": cx_.astype(np.float64),
                    "y_um": cy_.astype(np.float64),
                    "umap_x": src.cells.umap_x.to_numpy()[idx],
                    "umap_y": src.cells.umap_y.to_numpy()[idx],
                    "cluster_id": cell_cluster[idx],
                    "n_transcripts": src.cells.n_transcripts.to_numpy()[idx],
                }
            )
        )
        rows.append(idx)
    cells = pd.concat(cell_parts, ignore_index=True)
    cores = pd.DataFrame(core_recs)
    counts = sp.csr_matrix(src.expression[np.concatenate(rows)])
    side = SECTION_MARGIN_UM * 2 + cols * GRID_PITCH_UM
    rows_used = [math.ceil(len(range(s, n_cores, n_sec)) / cols) for s in range(n_sec)]
    sections = pd.DataFrame(
        [
            {
                "section_id": f"S{s + 1}",
                "he_image": None,
                "affine": None,
                "affine_source": None,
                "pixel_size": float(src.sections.pixel_size.iloc[0]),
                "he_pixel_size_um": float("nan"),
                "bounds_x0": 0.0,
                "bounds_y0": 0.0,
                "bounds_x1": side,
                "bounds_y1": SECTION_MARGIN_UM * 2 + rows_used[s] * GRID_PITCH_UM,
            }
            for s in range(n_sec)
        ]
    )
    record = DatasetRecord(
        name=cfg.name,
        title=cfg.title,
        license=cfg.license,
        citation=cfg.citation,
        synthetic=True,
        visibility=cfg.visibility,
        provenance={
            "derived_from": src.dataset.name,
            "source_provenance": src.dataset.provenance,
            "adapter": f"{cfg.adapter}@{ADAPTER_VERSION}",
            "pipeline_version": PIPELINE_VERSION,
            "seed": cfg.seed,
            "core_radius_um": cfg.core_radius_um,
            "base_cores": len(centers),
            "replicated": cfg.target_cells is not None,
            "split_largest": cfg.split_largest,
            "normalization": {"method": cfg.normalization, "scale_factor": cfg.scale_factor},
        },
    )
    return CanonicalDataset(
        record,
        sections,
        cores,
        cluster_table(cells.cluster_id, labels, colors),
        src.genes.copy(),
        cells,
        counts,
    )


def pick_cores(x: NDArray[Any], y: NDArray[Any], radius: float, rng: np.random.Generator) -> list[tuple[float, float]]:
    """Seeded dart throwing: centers ≥ 2r + gap apart whose disk is ≥ 80% occupied tissue bins."""
    b = COVERAGE_BIN_UM
    x0, y0 = x.min(), y.min()
    occ = np.zeros((int((y.max() - y0) // b) + 1, int((x.max() - x0) // b) + 1), bool)
    occ[((y - y0) // b).astype(int), ((x - x0) // b).astype(int)] = True
    rb = int(math.ceil(radius / b))
    oy, ox = np.mgrid[-rb : rb + 1, -rb : rb + 1]
    inside = (ox * b) ** 2 + (oy * b) ** 2 <= radius**2
    oy, ox = oy[inside], ox[inside]
    centers: list[tuple[float, float]] = []
    cand = np.column_stack(
        [
            rng.uniform(x.min() + radius, x.max() - radius, 20000),
            rng.uniform(y.min() + radius, y.max() - radius, 20000),
        ]
    )
    min_d = 2 * radius + CORE_GAP_UM
    for cx, cy in cand:
        if centers and np.min(np.hypot(*(np.array(centers) - [cx, cy]).T)) < min_d:
            continue
        iy, ix = int((cy - y0) // b) + oy, int((cx - x0) // b) + ox
        ok = (iy >= 0) & (iy < occ.shape[0]) & (ix >= 0) & (ix < occ.shape[1])
        cov = occ[iy[ok], ix[ok]].sum() / len(oy)
        if cov >= MIN_COVERAGE:
            centers.append((float(cx), float(cy)))
    return centers


def assign_patients(n_cores: int, n_patients: int | None, rng: np.random.Generator) -> list[str]:
    """Each patient gets ≥ 1 core; the rest go to random patients (so some have ≥ 2)."""
    n_p = n_patients or max(1, math.ceil(n_cores * 0.7))
    if n_p > n_cores:
        raise ValueError(f"{n_p} patients need at least as many cores (have {n_cores})")
    owners = np.concatenate([np.arange(n_p), rng.integers(0, n_p, n_cores - n_p)])
    rng.shuffle(owners)
    width = max(2, len(str(n_p)))
    return [f"P{o + 1:0{width}d}" for o in owners]


def clusters_for(src: CanonicalDataset, cfg: DatasetConfig) -> tuple[dict[str, str], dict[str, str], NDArray[Any]]:
    cl = src.clusters.sort_values("order")
    labels = dict(zip(cl.cluster_id, cl.label, strict=True))
    colors = dict(zip(cl.cluster_id, cl.color, strict=True))
    cell_cluster = src.cells.cluster_id.to_numpy().astype(object)
    if not cfg.split_largest:
        return labels, colors, cell_cluster.astype(str)
    from sklearn.cluster import KMeans
    from sklearn.decomposition import TruncatedSVD

    from ..assets import display_values

    largest = cl[cl.label.str.lower() != "unassigned"].sort_values("n_cells", ascending=False).head(cfg.split_largest)
    new_labels: dict[str, str] = {}
    new_colors: dict[str, str] = {}
    for cid in cl.cluster_id:
        if cid in set(largest.cluster_id):
            m = np.flatnonzero(cell_cluster == cid)
            disp = display_values(sp.csr_matrix(src.expression[m]), cfg.scale_factor).tocsr()
            pcs = TruncatedSVD(n_components=20, random_state=cfg.seed).fit_transform(disp)
            km = KMeans(n_clusters=2, n_init=10, random_state=cfg.seed).fit_predict(pcs)
            for k in (0, 1):
                sub = f"{cid}-sub-{k + 1}"
                new_labels[sub] = f"{labels[cid]} · sub {k + 1}"
                new_colors[sub] = colors[cid] if k == 0 else shade(colors[cid])
                cell_cluster[m[km == k]] = sub
        else:
            new_labels[cid], new_colors[cid] = labels[cid], colors[cid]
    return new_labels, new_colors, cell_cluster.astype(str)


def shade(hex_color: str) -> str:
    """Placeholder colour for the second sub-cluster until the NFR-7 palette lands (T-PIPE-PALETTE-01)."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    r, g, b = (int(v * 0.55) for v in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


__all__ = ["derive", "load", "load_config"]
