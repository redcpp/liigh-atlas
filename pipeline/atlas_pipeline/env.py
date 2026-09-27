"""Location of the data volumes. Data never lives on the internal disk (CLAUDE.md, BRIEF §4.2)."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"
CONFIG_DIR = REPO_ROOT / "pipeline" / "configs"


class DataRootError(RuntimeError):
    """$DATA_ROOT is unset or not a mounted volume."""


def data_root() -> Path:
    """Return $DATA_ROOT, refusing anything that is not a separate mounted volume."""
    raw = os.environ.get("DATA_ROOT")
    if not raw:
        raise DataRootError("DATA_ROOT is not set. Run: export DATA_ROOT=/Volumes/AtlasData")
    root = Path(raw)
    if not root.is_dir():
        raise DataRootError(
            f"{root} is not mounted. Ask the maintainer to run: hdiutil attach /Volumes/LaCie/AtlasData.sparsebundle"
        )
    if os.environ.get("ATLAS_ALLOW_UNMOUNTED_DATA_ROOT") != "1" and not _on_other_volume(root):
        raise DataRootError(
            f"{root} is on the same volume as the repository; refusing to write data to the internal disk"
        )
    return root


def _on_other_volume(path: Path) -> bool:
    return path.stat().st_dev != REPO_ROOT.stat().st_dev


def raw_dir(dataset: str) -> Path:
    return data_root() / "raw" / dataset


def canonical_dir(dataset: str) -> Path:
    return data_root() / "canonical" / dataset


def derived_dir(dataset: str) -> Path:
    return data_root() / "derived" / dataset


def build_dir(dataset: str) -> Path:
    return data_root() / "build" / dataset
