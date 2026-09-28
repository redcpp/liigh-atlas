"""Xenium Onboard Analysis version gate (ADR-0009 condition a).

Our readers are tested against specific ``analysis_sw_version`` values from ``experiment.xenium``.
Any other version fails loudly: file layouts and column names change between releases, and a new
version is supported only after the oracle test (tests/test_data_ovarian.py) passes on it.
"""

from __future__ import annotations

from typing import Any

SUPPORTED_ANALYSIS_VERSIONS: tuple[str, ...] = ("xenium-3.0.0.15",)  # ovarian-10x dev data


class UnsupportedXeniumVersionError(RuntimeError):
    pass


def check_version(experiment: dict[str, Any]) -> str:
    version = experiment.get("analysis_sw_version")
    if version not in SUPPORTED_ANALYSIS_VERSIONS:
        raise UnsupportedXeniumVersionError(
            f"experiment.xenium analysis_sw_version={version!r} is not a tested version "
            f"{list(SUPPORTED_ANALYSIS_VERSIONS)}; run the spatialdata-io oracle test on it, then add it to "
            "atlas_pipeline.xenium.SUPPORTED_ANALYSIS_VERSIONS"
        )
    return str(version)
