from __future__ import annotations

import os
from pathlib import Path

import pytest

DATA_ROOT = os.environ.get("DATA_ROOT", "")


def data_available() -> bool:
    return bool(DATA_ROOT) and (Path(DATA_ROOT) / "raw" / "ovarian-10x" / "members.txt").exists()


requires_data = pytest.mark.skipif(not data_available(), reason="$DATA_ROOT with ovarian-10x not mounted")


@pytest.fixture(scope="session")
def fixture_run():
    """One end-to-end fixture pipeline run shared by the tests (no $DATA_ROOT needed)."""
    from atlas_pipeline.run import run

    return run("fixture")
