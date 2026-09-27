"""Asset builders (ADR-0002, ADR-0003): typed binary columns, per-gene expression, JSON tables, manifest."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
from numpy.typing import NDArray

from .contract import CanonicalDataset

log = logging.getLogger(__name__)
SCHEMA_VERSION = 1
U16_MAX = 65535


# ---------- quantization (T-PIPE-QUANT-01) ----------
@dataclass(frozen=True)
class Quant:
    offset: float
    scale: float

    def encode(self, v: NDArray[Any]) -> NDArray[Any]:
        q = np.rint((np.asarray(v, dtype=np.float64) - self.offset) / self.scale)
        return np.clip(q, 0, U16_MAX).astype(np.uint16)

    def decode(self, q: NDArray[Any]) -> NDArray[Any]:
        return self.offset + q.astype(np.float64) * self.scale


def fit_quant(lo: float, hi: float) -> Quant:
    span = max(hi - lo, 1e-9)
    return Quant(offset=float(lo), scale=float(span / U16_MAX))


# ---------- ordering ----------
def morton_code(qx: NDArray[Any], qy: NDArray[Any]) -> NDArray[Any]:
    """Interleave the bits of two uint16 arrays into uint32 Z-order codes."""

    def spread(v: NDArray[Any]) -> NDArray[Any]:
        v = v.astype(np.uint32)
        v = (v | (v << 8)) & np.uint32(0x00FF00FF)
        v = (v | (v << 4)) & np.uint32(0x0F0F0F0F)
        v = (v | (v << 2)) & np.uint32(0x33333333)
        v = (v | (v << 1)) & np.uint32(0x55555555)
        return v

    return np.asarray(spread(qx) | (spread(qy) << np.uint32(1)), dtype=np.uint32)


def cell_order(ds: CanonicalDataset, xy_quant: dict[str, Quant]) -> NDArray[Any]:
    """Permutation sorting cells by section → core → Morton(x, y) → cell_id (stable, deterministic)."""
    c = ds.cells
    sec_rank = {s: i for i, s in enumerate(sorted(ds.sections.section_id))}
    core_rank = {k: i for i, k in enumerate(core_sequence(ds))}
    qx = np.empty(len(c), np.uint16)
    qy = np.empty(len(c), np.uint16)
    for sid, q in xy_quant.items():
        m = (c.section_id == sid).to_numpy()
        qx[m], qy[m] = q.encode(c.x_um.to_numpy()[m]), q.encode(c.y_um.to_numpy()[m])
    keys = (
        c.cell_id.to_numpy(),
        morton_code(qx, qy),
        c.core_id.map(core_rank).to_numpy(),
        c.section_id.map(sec_rank).to_numpy(),
    )
    return np.asarray(np.lexsort(keys))


def core_sequence(ds: CanonicalDataset) -> list[str]:
    cores = ds.cores.sort_values(["section_id", "core_id"])
    return list(cores.core_id)


# ---------- expression (T-PIPE-EXPR-01) ----------
def display_values(counts: sp.csr_matrix, scale_factor: float) -> sp.csc_matrix:
    """log1p(counts / n_counts_total × scale_factor), per cell; returned column-major (per gene)."""
    totals = np.asarray(counts.sum(axis=1), dtype=np.float64).ravel()
    inv = np.divide(scale_factor, totals, out=np.zeros_like(totals), where=totals > 0)
    norm = sp.diags(inv) @ counts.astype(np.float64)
    norm = sp.csr_matrix(norm)
    norm.data = np.log1p(norm.data)
    return norm.tocsc()


def quantize_gene(values: NDArray[Any]) -> tuple[NDArray[Any], float]:
    """uint8 with 0 reserved for not detected: q = max(1, round(255·v/max_v)) for v > 0."""
    max_v = float(values.max()) if values.size else 0.0
    if max_v <= 0:
        return np.zeros(values.shape, np.uint8), 0.0
    q = np.rint(255.0 * values / max_v)
    return np.clip(q, 1, 255).astype(np.uint8), max_v


def leb128(values: NDArray[Any]) -> bytes:
    """Unsigned LEB128 varint encoding of a uint32 array (vectorized)."""
    v = values.astype(np.uint64)
    n_bytes = np.ones(len(v), np.int64)
    for k in (7, 14, 21, 28):
        n_bytes += v >= (1 << k)
    out = np.empty(int(n_bytes.sum()), np.uint8)
    starts = np.concatenate([[0], np.cumsum(n_bytes)[:-1]])
    for i in range(5):
        m = n_bytes > i
        byte = ((v[m] >> np.uint64(7 * i)) & np.uint64(0x7F)).astype(np.uint8)
        more = (n_bytes[m] > i + 1).astype(np.uint8) << 7
        out[starts[m] + i] = byte | more
    return out.tobytes()


def unleb128(buf: bytes, count: int) -> NDArray[Any]:
    out = np.empty(count, np.uint32)
    pos = 0
    for i in range(count):
        shift = 0
        val = 0
        while True:
            b = buf[pos]
            pos += 1
            val |= (b & 0x7F) << shift
            shift += 7
            if b < 0x80:
                break
        out[i] = val
    return out


def encode_gene(n_cells: int, idx: NDArray[Any], q: NDArray[Any]) -> bytes:
    """Header: uint8 format (0 dense, 1 sparse), uint32 nnz; then payload. Smaller format wins."""
    nnz = len(idx)
    dense_len = n_cells
    deltas = np.diff(np.concatenate([[0], idx])).astype(np.uint32) if nnz else np.zeros(0, np.uint32)
    if nnz:
        deltas[1:] = np.diff(idx).astype(np.uint32)
        deltas[0] = idx[0]
    sparse_payload = leb128(deltas) + q.tobytes()
    header = np.array([nnz], dtype="<u4").tobytes()
    if len(sparse_payload) < dense_len:
        return b"\x01" + header + sparse_payload
    dense = np.zeros(n_cells, np.uint8)
    dense[idx] = q
    return b"\x00" + header + dense.tobytes()


def decode_gene(buf: bytes, n_cells: int) -> NDArray[Any]:
    fmt = buf[0]
    nnz = int(np.frombuffer(buf[1:5], dtype="<u4")[0])
    body = buf[5:]
    if fmt == 0:
        return np.frombuffer(body, np.uint8).copy()
    vals = np.frombuffer(body[len(body) - nnz :], np.uint8)
    deltas = unleb128(body[: len(body) - nnz], nnz)
    out = np.zeros(n_cells, np.uint8)
    out[np.cumsum(deltas.astype(np.int64))] = vals
    return out


# ---------- writing ----------
@dataclass
class Writer:
    root: Path
    files: dict[str, dict[str, Any]] = field(default_factory=dict)

    def write(self, rel: str, data: bytes, family: str, **meta: Any) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.files[rel] = {
            "family": family,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            **meta,
        }

    def json(self, rel: str, obj: Any, family: str, **meta: Any) -> None:
        self.write(rel, dumps(obj).encode(), family, **meta)

    def sizes(self) -> dict[str, tuple[int, int]]:
        fam: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for info in self.files.values():
            fam[info["family"]][0] += 1
            fam[info["family"]][1] += info["bytes"]
        return {k: (v[0], v[1]) for k, v in sorted(fam.items())}


def dumps(obj: Any) -> str:
    return json.dumps(_round(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _round(obj: Any) -> Any:
    if isinstance(obj, float):
        return float(f"{obj:.10g}")
    if isinstance(obj, dict):
        return {str(k): _round(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_round(v) for v in obj]
    if isinstance(obj, np.generic):
        return _round(obj.item())
    return obj


@dataclass
class BuildResult:
    staging: Path
    writer: Writer
    manifest: dict[str, Any]
    order: NDArray[Any]
    xy_quant: dict[str, Quant]
    umap_quant: tuple[Quant, Quant]
    quant_errors: dict[str, float]


def build_assets(ds: CanonicalDataset, staging: Path, scale_factor: float) -> BuildResult:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    w = Writer(staging)
    secs = ds.sections.sort_values("section_id").reset_index(drop=True)
    sec_rows: list[Any] = list(secs.itertuples())
    xy_quant: dict[str, Quant] = {
        s.section_id: fit_quant(min(s.bounds_x0, s.bounds_y0), max(s.bounds_x1, s.bounds_y1)) for s in sec_rows
    }
    order = cell_order(ds, xy_quant)
    cells = ds.cells.iloc[order].reset_index(drop=True)
    counts = ds.expression[order]
    n = len(cells)

    # cells/*
    ux, uy = cells.umap_x.to_numpy(np.float64), cells.umap_y.to_numpy(np.float64)
    umap_q = (fit_quant(ux.min(), ux.max()), fit_quant(uy.min(), uy.max()))
    qu = np.stack([umap_q[0].encode(ux), umap_q[1].encode(uy)], axis=1)
    w.write(
        "cells/umap.u16",
        qu.astype("<u2").tobytes(),
        "cells",
        dtype="uint16",
        shape=[n, 2],
        offset=[umap_q[0].offset, umap_q[1].offset],
        scale=[umap_q[0].scale, umap_q[1].scale],
    )
    qxy = np.empty((n, 2), np.uint16)
    errs = {
        "umap_x_frac": _err(umap_q[0], ux, qu[:, 0]) / max(np.ptp(ux), 1e-12),
        "umap_y_frac": _err(umap_q[1], uy, qu[:, 1]) / max(np.ptp(uy), 1e-12),
    }
    for sid, q in xy_quant.items():
        m = (cells.section_id == sid).to_numpy()
        x, y = cells.x_um.to_numpy()[m], cells.y_um.to_numpy()[m]
        qxy[m, 0], qxy[m, 1] = q.encode(x), q.encode(y)
        errs["xy_um[" + str(sid) + "]"] = max(_err(q, x, qxy[m, 0]), _err(q, y, qxy[m, 1]))
    w.write(
        "cells/xy.u16",
        qxy.astype("<u2").tobytes(),
        "cells",
        dtype="uint16",
        shape=[n, 2],
        quantization="per section: see sections.json xy_offset / xy_scale",
    )

    clusters = ds.clusters.sort_values("order").reset_index(drop=True)
    if len(clusters) > 255:
        raise ValueError("more than 255 clusters do not fit uint8")
    cl_idx = cells.cluster_id.map({c: i for i, c in enumerate(clusters.cluster_id)}).to_numpy(np.uint8)
    w.write("cells/cluster.u8", cl_idx.tobytes(), "cells", dtype="uint8", shape=[n])
    core_ids = core_sequence(ds)
    core_idx = cells.core_id.map({c: i for i, c in enumerate(core_ids)}).to_numpy(np.int64)
    w.write("cells/core.u16", core_idx.astype("<u2").tobytes(), "cells", dtype="uint16", shape=[n])
    ntx = cells.n_transcripts.to_numpy()
    n_clip = int((ntx > U16_MAX).sum())
    w.write(
        "cells/ntx.u16",
        np.clip(ntx, 0, U16_MAX).astype("<u2").tobytes(),
        "cells",
        dtype="uint16",
        shape=[n],
        clipped=n_clip,
    )

    # tables
    w.json(
        "clusters.json",
        [
            {
                "id": r.cluster_id,
                "label": r.label,
                "color": r.color,
                "order": int(r.order),
                "n_cells": int(r.n_cells),
            }
            for r in list[Any](clusters.itertuples())
        ],
        "tables",
    )
    cores_df = ds.cores.set_index("core_id").loc[core_ids]
    ranges: list[list[int]] = []
    for i in range(len(core_ids)):
        pos = np.flatnonzero(core_idx == i)
        if len(pos) == 0 or pos[-1] - pos[0] + 1 != len(pos):
            raise ValueError(f"core {core_ids[i]} cells are not contiguous after ordering")
        ranges.append([int(pos[0]), int(pos[-1]) + 1])
    w.json(
        "cores.json",
        [
            {
                "id": cid,
                "section": r.section_id,
                "patient": r.patient_id,
                "kind": r.kind,
                "center_um": [r.center_x_um, r.center_y_um],
                "radius_um": r.radius_um,
                "bbox_um": [r.bbox_x0, r.bbox_y0, r.bbox_x1, r.bbox_y1],
                "cell_range": ranges[i],
                "clinical": {},
            }
            for i, (cid, r) in enumerate(cores_df.iterrows())
        ],
        "tables",
    )
    w.json(
        "sections.json",
        [
            {
                "id": s.section_id,
                "pixel_size_um": s.pixel_size,
                "bounds_um": [s.bounds_x0, s.bounds_y0, s.bounds_x1, s.bounds_y1],
                "xy_offset": xy_quant[s.section_id].offset,
                "xy_scale": xy_quant[s.section_id].scale,
                "he": None
                if s.he_image is None
                else {
                    "affine_um_to_he_px": _mat(s.affine),
                    "affine_source": _mat(s.affine_source),
                    "affine_source_direction": "H&E px -> Xenium px",
                    "source_pixel_size_um": s.he_pixel_size_um,
                },
            }
            for s in sec_rows
        ],
        "tables",
    )

    # expression
    disp = display_values(counts, scale_factor)
    genes_out = []
    for j, g in enumerate(ds.genes.itertuples()):
        lo, hi = disp.indptr[j], disp.indptr[j + 1]
        idx = disp.indices[lo:hi].astype(np.int64)
        srt = np.argsort(idx, kind="stable")
        qv, max_v = quantize_gene(disp.data[lo:hi][srt])
        rel = f"expr/{g.gene_id}.bin"
        w.write(rel, encode_gene(n, idx[srt], qv), "expression")
        genes_out.append(
            {
                "id": g.gene_id,
                "symbol": g.symbol,
                "panel": g.panel,
                "max_v": max_v,
                "nnz": int(hi - lo),
                "file": rel,
            }
        )
    w.json("genes.json", genes_out, "tables")
    return BuildResult(staging, w, {}, order, xy_quant, umap_q, errs)


def _err(q: Quant, v: NDArray[Any], enc: NDArray[Any]) -> float:
    return float(np.max(np.abs(q.decode(enc) - v))) if len(v) else 0.0


def _mat(v: Any) -> list[list[float]]:
    return np.asarray(v, dtype=float).reshape(3, 3).tolist()


INDEX_FAMILIES = ("expression", "he")


def write_manifest(res: BuildResult, ds: CanonicalDataset) -> dict[str, Any]:
    """Manifest lists every file of the initial families; expression and H&E go into index files whose
    hashes the manifest pins (Merkle style), so the manifest stays small. Release = sha256[:12]."""
    w = res.writer
    indexes: dict[str, dict[str, Any]] = {}
    for fam in INDEX_FAMILIES:
        entries = {k: [v["bytes"], v["sha256"]] for k, v in sorted(w.files.items()) if v["family"] == fam}
        if entries:
            w.json(f"index/{fam}.json", entries, "index")
            indexes[fam] = {"files": len(entries), "bytes": sum(e[0] for e in entries.values())}
    listed = {k: v for k, v in sorted(w.files.items()) if v["family"] not in INDEX_FAMILIES}
    record = ds.dataset.model_dump()
    record.pop("release", None)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset": record,
        "counts": {
            "cells": len(ds.cells),
            "genes": len(ds.genes),
            "clusters": len(ds.clusters),
            "cores": len(ds.cores),
            "sections": len(ds.sections),
            "patients": int(ds.cores.patient_id.nunique()),
        },
        "files": listed,
        "indexes": indexes,
        "sizes": {fam: {"files": nf, "bytes": nb} for fam, (nf, nb) in w.sizes().items()},
    }
    body = dumps(manifest).encode()
    release = hashlib.sha256(body).hexdigest()[:12]
    (res.staging / "manifest.json").write_bytes(body)
    manifest["release"] = release
    res.manifest = manifest
    return manifest
