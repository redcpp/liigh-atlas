"""env guard, T-PIPE-PRIV-01 privacy filter, CLI."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from atlas_pipeline import env, logs
from atlas_pipeline.__main__ import main
from atlas_pipeline.config import load_config


def test_data_root_refuses_missing_and_internal_disk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DATA_ROOT", raising=False)
    with pytest.raises(env.DataRootError, match="not set"):
        env.data_root()
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "nope"))
    with pytest.raises(env.DataRootError, match="hdiutil attach"):
        env.data_root()
    monkeypatch.setenv("DATA_ROOT", str(env.REPO_ROOT))
    monkeypatch.delenv("ATLAS_ALLOW_UNMOUNTED_DATA_ROOT", raising=False)
    with pytest.raises(env.DataRootError, match="internal disk"):
        env.data_root()
    monkeypatch.setenv("ATLAS_ALLOW_UNMOUNTED_DATA_ROOT", "1")
    assert env.build_dir("x") == env.REPO_ROOT / "build" / "x"
    assert env.derived_dir("x").name == "x" and env.canonical_dir("x").parent.name == "canonical"


def test_cli_exit_codes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["data", "--tier", "list"]) == 0
    assert "core:" in capsys.readouterr().out
    monkeypatch.delenv("DATA_ROOT", raising=False)
    assert main(["data", "--tier", "meta"]) == 3
    assert main(["run", "ovarian-10x"]) == 3


def test_privacy_filter_drops_cell_level_records_for_private(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    flt = logs.setup(tmp_path / "p.log", private=True)
    lg = logging.getLogger("atlas_pipeline.test")
    lg.info("aggregate: %d cells", 10)
    lg.info("cell %s value %f", "abc-1", 1.0, extra={"cell_level": True})
    for h in logging.getLogger().handlers:
        h.flush()
    text = (tmp_path / "p.log").read_text()
    assert "aggregate: 10 cells" in text and "abc-1" not in text and flt.rejected == 1
    public = logs.PrivacyFilter(private=False)
    rec = logging.LogRecord("x", logging.INFO, "", 0, "cell", None, None)
    rec.cell_level = True
    assert public.filter(rec)


def test_config_errors() -> None:
    with pytest.raises(FileNotFoundError, match="known"):
        load_config("does-not-exist")
    assert load_config("scale").expected.n_clusters == 23
