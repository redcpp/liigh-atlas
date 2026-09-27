"""Dataset configs: `pipeline/configs/<name>.toml`. Lab-specific unknowns live in config, not code."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .env import CONFIG_DIR


class Expected(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_cells: int | None = None
    min_cells: int | None = None
    median_transcripts: float | None = None
    n_clusters: int | None = None
    min_cores: int | None = None
    n_patients: int | None = None
    n_sections: int | None = None


class DatasetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    adapter: str
    title: str
    license: str
    citation: str
    synthetic: bool
    visibility: Literal["public", "private"] = "public"
    seed: int = 0
    source: str | None = None  # dataset this one is derived from (synthetic-tma, scale)
    he: bool = False  # build the H&E pyramid
    align_test: bool = False  # run T-PIPE-ALIGN-01/02 as a build check
    normalization: str = "log1p_cp10k"
    scale_factor: float = 1e4
    core_radius_um: float = 500.0
    n_patients: int | None = None
    target_cells: int | None = None
    min_cores: int | None = None
    n_sections: int = 1
    split_largest: int = 0
    max_total_bytes: int = 5 * 10**9  # NFR-13
    expected: Expected = Expected()


def load_config(name: str, config_dir: Path = CONFIG_DIR) -> DatasetConfig:
    path = config_dir / f"{name}.toml"
    if not path.exists():
        known = sorted(p.stem for p in config_dir.glob("*.toml"))
        raise FileNotFoundError(f"no dataset config {name!r}; known: {known}")
    with path.open("rb") as f:
        return DatasetConfig.model_validate(tomllib.load(f))
