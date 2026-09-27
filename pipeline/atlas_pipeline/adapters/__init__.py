"""Source adapters: one per source, each producing the canonical dataset (DATA_CONTRACT §9)."""

from __future__ import annotations

from collections.abc import Callable

from ..config import DatasetConfig
from ..contract import CanonicalDataset
from ..rawio import RawFileLog


def get_adapter(name: str) -> Callable[[DatasetConfig, RawFileLog], CanonicalDataset]:
    if name == "ovarian-10x":
        from .ovarian import load
    elif name in ("synthetic-tma", "scale"):
        from .synthetic import load
    elif name == "fixture":
        from .fixture import load
    else:
        raise KeyError(f"unknown adapter {name!r}")
    return load
