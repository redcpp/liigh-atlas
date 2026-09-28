"""ADR-0009 (a): only tested Xenium analysis versions are accepted."""

import pytest

from atlas_pipeline.xenium import SUPPORTED_ANALYSIS_VERSIONS, UnsupportedXeniumVersionError, check_version


def test_supported_version_passes() -> None:
    assert check_version({"analysis_sw_version": "xenium-3.0.0.15"}) == "xenium-3.0.0.15"
    assert "xenium-3.0.0.15" in SUPPORTED_ANALYSIS_VERSIONS


@pytest.mark.parametrize("exp", [{"analysis_sw_version": "xenium-4.0.0.1"}, {"analysis_sw_version": None}, {}])
def test_unknown_version_fails_loudly(exp: dict[str, object]) -> None:
    with pytest.raises(UnsupportedXeniumVersionError, match="not a tested version"):
        check_version(exp)
