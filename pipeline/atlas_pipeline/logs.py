"""Logging setup, with the privacy filter for private datasets (TECH_SPEC §10, T-PIPE-PRIV-01)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


class PrivacyFilter(logging.Filter):
    """For private datasets, drop any record marked as cell-level (``extra={"cell_level": True}``)."""

    def __init__(self, private: bool) -> None:
        super().__init__()
        self.private = private
        self.rejected = 0
        self._last: int | None = None  # one record passes through every handler; count it once

    def filter(self, record: logging.LogRecord) -> bool:
        if self.private and getattr(record, "cell_level", False):
            if self._last != id(record):
                self.rejected += 1
                self._last = id(record)
            return False
        return True


def setup(log_file: Path | None, private: bool) -> PrivacyFilter:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.INFO)
    flt = PrivacyFilter(private)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, mode="w"))
    for h in handlers:
        h.setFormatter(fmt)
        h.addFilter(flt)
        root.addHandler(h)
    for noisy in ("numba", "matplotlib", "PIL", "h5py", "fsspec"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return flt
