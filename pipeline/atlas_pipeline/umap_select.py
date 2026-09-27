"""Dev UMAP selection (Gate 0, TECH_SPEC §2, T-PIPE-UMAP-01).

Scores the provided Xenium UMAP and a seeded scanpy recompute by kNN cluster coherence (share of the
15 nearest UMAP neighbours, self excluded, that carry the cell's 10x group) and keeps the higher one
(ties keep the provided one). The recompute is cached under ``$DATA_ROOT/derived/<dataset>/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp
from numpy.typing import NDArray
from sklearn.neighbors import NearestNeighbors

from .config import DatasetConfig
from .env import derived_dir
from .rawio import RawFileLog

log = logging.getLogger(__name__)
K = 15
UMAP_PARAMS: dict[str, Any] = {
    "normalize_total": 1e4,
    "log1p": True,
    "pca_n_comps": 50,
    "pca_solver": "arpack",
    "n_neighbors": 15,
    "umap_min_dist": 0.5,
}


def knn_coherence(emb: NDArray[Any], labels: NDArray[Any], k: int = K) -> float:
    """Mean over cells of the fraction of the k nearest neighbours (self excluded) sharing its label."""
    nn = NearestNeighbors(n_neighbors=k + 1, n_jobs=-1).fit(emb)
    idx = nn.kneighbors(emb, return_distance=False)
    rows = np.arange(len(emb))[:, None]
    # drop self wherever it appears (duplicates can push it out of column 0), keep the first k others
    others = np.where(idx == rows, -1, idx)
    keep = np.argsort(others == -1, axis=1, kind="stable")[:, :k]
    neigh = np.take_along_axis(others, keep, axis=1)
    lab = np.asarray(labels)
    return float(np.mean(lab[neigh] == lab[:, None]))


def matrix_hash(counts: sp.csr_matrix) -> str:
    h = hashlib.sha256()
    h.update(np.asarray(counts.shape, dtype=np.int64).tobytes())
    for arr in (
        counts.indptr.astype(np.int64),
        counts.indices.astype(np.int32),
        counts.data.astype(np.int32),
    ):
        h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()


def recompute_umap(counts: sp.csr_matrix, seed: int) -> NDArray[Any]:
    import anndata as ad
    import scanpy as sc

    if (np.asarray(counts.sum(axis=1)).ravel() == 0).any():
        raise ValueError("recompute_umap needs cells with ≥ 1 transcript")
    adata = ad.AnnData(X=counts.astype(np.float32))
    sc.pp.normalize_total(adata, target_sum=UMAP_PARAMS["normalize_total"])
    sc.pp.log1p(adata)
    sc.pp.pca(adata, n_comps=UMAP_PARAMS["pca_n_comps"], svd_solver=UMAP_PARAMS["pca_solver"], random_state=seed)
    sc.pp.neighbors(adata, n_neighbors=UMAP_PARAMS["n_neighbors"], random_state=seed)
    sc.tl.umap(adata, min_dist=UMAP_PARAMS["umap_min_dist"], random_state=seed)
    return np.asarray(adata.obsm["X_umap"], dtype=np.float32)


def cached_recompute(
    counts: sp.csr_matrix, cell_ids: NDArray[Any], dataset: str, seed: int
) -> tuple[NDArray[Any], dict[str, Any]]:
    from importlib.metadata import version

    mhash = matrix_hash(counts)
    params = {**UMAP_PARAMS, "random_state": seed, "input_matrix_sha256": mhash}
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
    out_dir = derived_dir(dataset)
    path, sidecar = out_dir / f"umap-{key}.parquet", out_dir / f"umap-{key}.json"
    if path.exists() and sidecar.exists():
        log.info("UMAP recompute: cache hit %s (not recomputed)", path)
        df = pd.read_parquet(path)
        if not np.array_equal(df.cell_id.to_numpy(), cell_ids):
            raise ValueError(f"cached UMAP {path} does not match the cell order")
        emb: NDArray[Any] = df[["umap_1", "umap_2"]].to_numpy(np.float32)
    else:
        log.info("UMAP recompute: cache miss, computing (%d cells)", counts.shape[0])
        emb = recompute_umap(counts, seed)
        if not np.isfinite(emb).all():
            raise ValueError("recomputed UMAP has non-finite values")
        out_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        pd.DataFrame({"cell_id": cell_ids, "umap_1": emb[:, 0], "umap_2": emb[:, 1]}).to_parquet(tmp, index=False)
        tmp.replace(path)
        meta = {
            **params,
            "libraries": {lib: version(lib) for lib in ("scanpy", "anndata", "umap-learn", "scikit-learn")},
        }
        sidecar.write_text(json.dumps(meta, indent=2, sort_keys=True))
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return emb, {"params": params, "cache_key": key, "embedding_sha256": file_hash}


def read_provided(outs: Path, cell_ids: NDArray[Any], rawlog: RawFileLog) -> tuple[NDArray[Any], NDArray[Any]]:
    """Provided Xenium UMAP in ``cell_ids`` order, plus the mask of cells it covers."""
    proj = rawlog.use(outs / "analysis/umap/gene_expression_2_components/projection.csv")
    df = pd.read_csv(proj).set_index("Barcode").reindex(cell_ids)
    present = ~df.isna().any(axis=1).to_numpy()
    return df[["UMAP-1", "UMAP-2"]].to_numpy(np.float32), present


def select_umap(
    counts: sp.csr_matrix,
    cell_ids: NDArray[Any],
    labels: NDArray[Any],
    outs: Path,
    cfg: DatasetConfig,
    rawlog: RawFileLog,
    fill_label: str = "unassigned",
) -> tuple[NDArray[Any], dict[str, Any]]:
    provided, present = read_provided(outs, cell_ids, rawlog)
    n_tx = np.asarray(counts.sum(axis=1)).ravel()
    if (n_tx[~present] > 0).any():
        raise ValueError(f"provided UMAP misses {int((~present & (n_tx > 0)).sum())} cells with transcripts")
    rec_part, meta = cached_recompute(counts[present], cell_ids[present], cfg.name, cfg.seed)
    recomputed = np.full_like(provided, np.nan)
    recomputed[present] = rec_part
    # score both on the cells the provided embedding covers, so the comparison is like for like
    s_prov = knn_coherence(provided[present], labels[present])
    s_rec = knn_coherence(recomputed[present], labels[present])
    choice = "recomputed" if s_rec > s_prov else "provided"
    log.info("UMAP kNN coherence (k=%d): provided=%.4f recomputed=%.4f -> using %s", K, s_prov, s_rec, choice)
    n_missing = int((~present).sum())
    chosen = recomputed if choice == "recomputed" else provided
    if n_missing:
        # cells with 0 transcripts have no expression profile, so neither embedding can place them
        # (10x leaves them out too). They sit at the median of their group (Unassigned) so every cell
        # has finite coordinates; the count is in provenance.
        grp = present & (labels == fill_label)
        chosen[~present] = np.median(chosen[grp], axis=0)
    prov = {
        "source": choice,
        "knn_coherence": {
            "k": K,
            "scored_cells": int(present.sum()),
            "provided": round(s_prov, 6),
            "recomputed": round(s_rec, 6),
        },
        "zero_transcript_cells_placed_at_group_median": n_missing,
        "recompute": meta,
    }
    return chosen, prov
