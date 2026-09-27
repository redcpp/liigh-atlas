"""`fixture` adapter: the small committed dataset in ``fixtures/fixture/`` (CI, unit tests).

It is a 600 µm window of the ovarian-10x data cut into 4 small cores (one patient with 2 cores), with
the matching crop of the H&E and its alignment, so every stage — H&E pyramid and alignment test
included — runs without ``$DATA_ROOT``. Built by ``python -m atlas_pipeline make-fixture``.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import scipy.sparse as sp

from ..config import DatasetConfig
from ..contract import CanonicalDataset, DatasetRecord
from ..env import FIXTURES_DIR
from ..rawio import RawFileLog
from .common import he_affine

FIXTURE_DIR = FIXTURES_DIR / "fixture"


def load(cfg: DatasetConfig, rawlog: RawFileLog) -> CanonicalDataset:
    d = FIXTURE_DIR
    tables = {
        n: pd.read_parquet(rawlog.use(d / f"{n}.parquet", "fixture")) for n in ("cells", "genes", "clusters", "cores")
    }
    sections = pd.DataFrame(json.loads(rawlog.use(d / "sections.json", "fixture").read_text()))
    sections["affine"] = [
        he_affine(np.asarray(a, float).reshape(3, 3), float(ps)).ravel().tolist()
        for a, ps in zip(sections.affine_source, sections.pixel_size, strict=True)
    ]
    sections = sections[
        [
            "section_id",
            "he_image",
            "affine",
            "affine_source",
            "pixel_size",
            "he_pixel_size_um",
            "bounds_x0",
            "bounds_y0",
            "bounds_x1",
            "bounds_y1",
        ]
    ]
    npz = np.load(rawlog.use(d / "counts.npz", "fixture"))
    counts = sp.csr_matrix((npz["data"], npz["indices"], npz["indptr"]), shape=tuple(npz["shape"]))
    info = json.loads(rawlog.use(d / "dataset.json", "fixture").read_text())
    record = DatasetRecord(
        name=cfg.name,
        title=cfg.title,
        license=cfg.license,
        citation=cfg.citation,
        synthetic=True,
        visibility=cfg.visibility,
        provenance=info["provenance"],
    )
    return CanonicalDataset(
        record,
        sections,
        tables["cores"],
        tables["clusters"],
        tables["genes"],
        tables["cells"],
        counts.astype(np.int32),
    )
