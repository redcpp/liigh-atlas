"""T-PIPE-GUARD-01."""

from pathlib import Path

import pytest

from atlas_pipeline.rawio import ForbiddenRawFileError, RawFileLog, is_forbidden


@pytest.mark.parametrize(
    "name",
    [
        "outs/transcripts.parquet",
        "outs/transcripts.zarr.zip",
        "outs/morphology.ome.tif",
        "outs/morphology_focus/morphology_focus_0000.ome.tif",
        "outs/cells.zarr.zip",
        "outs/analysis.zarr.zip",
    ],
)
def test_guard_refuses_forbidden(name: str) -> None:
    log = RawFileLog()
    assert is_forbidden(Path(name))
    with pytest.raises(ForbiddenRawFileError):
        log.use(Path("/data") / name)
    assert log.opened == []


def test_log_lists_every_file_once() -> None:
    log = RawFileLog()
    for p in ["outs/cells.parquet", "outs/cell_feature_matrix.h5", "outs/cells.parquet"]:
        log.use(Path(p))
    assert [p for _, p in log.opened] == ["outs/cells.parquet", "outs/cell_feature_matrix.h5"]
    text = log.render()
    assert "Files opened (2)" in text and "NONE" in text
    log.opened.append(("raw", "outs/transcripts.parquet"))  # simulate a bypass
    assert log.forbidden_opened() == ["outs/transcripts.parquet"]
    assert "transcripts.parquet" in log.render().splitlines()[-1]
