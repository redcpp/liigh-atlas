"""Gate 1: without the test-only cells.zarr.zip the oracle skips with an explicit reason."""

from pathlib import Path

from .test_data_ovarian import oracle_skip_reason


def test_oracle_skip_reason(tmp_path: Path) -> None:
    reason = oracle_skip_reason(tmp_path)
    assert reason is not None and reason.endswith("the pipeline never reads it)")
    assert "test-only input" in reason and "cells.zarr.zip" in reason and "skipped" in reason
    (tmp_path / "cells.zarr.zip").write_bytes(b"")
    assert oracle_skip_reason(tmp_path) is None
