"""T-PIPE-DATA-01 (unit part): idempotent verification, md5 / size checks, fetch only what is missing."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from atlas_pipeline import verify as v


def make_layout(root: Path) -> dict[str, bytes]:
    supp = root / "supplemental"
    supp.mkdir(parents=True)
    contents = {}
    md5_lines = []
    for _, rel, _ in v.TIERS["meta"] + v.TIERS["he"]:
        data = rel.encode() * 10
        (root / rel).write_bytes(data)
        contents[rel] = data
        md5_lines.append(f"{hashlib.md5(data).hexdigest()} {Path(rel).name}")
    (supp / "md5.expected").write_text("\n".join(md5_lines))
    members = []
    for tier in ("core", "boundaries"):
        for method, rel, member in v.TIERS[tier]:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            data = b"x" * 150_000
            p.write_bytes(data)
            if method == "size":
                members.append(f"   {len(data) / 1e6:.1f} MB  {member}")
    members.append("   13326.9 MB  morphology.ome.tif")
    (root / "members.txt").write_text("\n".join(members))
    (root / "urls.env").write_text(
        "BUNDLE_URL=https://example.invalid/bundle.zip\nHE_URL='https://example.invalid/he'\n# c\n"
    )
    return contents


def no_network(*_a: object) -> None:
    raise AssertionError("must not download anything that is present")


def test_idempotent_all_present(tmp_path: Path) -> None:
    make_layout(tmp_path)
    for _ in range(2):
        checks = v.verify(
            tmp_path, ["meta", "core", "he", "boundaries"], downloader=no_network, bundle_fetcher=no_network
        )
        assert {c.status for c in checks} == {"ok"}
    table = v.render(checks)
    assert "15 files checked, 0 downloaded, 0 failed" in table
    assert "tier" in table.splitlines()[0]


def test_md5_mismatch_and_size_mismatch(tmp_path: Path) -> None:
    make_layout(tmp_path)
    (tmp_path / v.TIERS["meta"][0][1]).write_bytes(b"corrupt")
    (tmp_path / "outs/cells.parquet").write_bytes(b"short")
    (tmp_path / v.TIERS["core"][3][1]).unlink()  # unpacked projection.csv
    checks = v.verify(tmp_path, ["meta", "core"], downloader=no_network, bundle_fetcher=no_network)
    status = {c.path: c.status for c in checks}
    assert status[v.TIERS["meta"][0][1]] == "MISMATCH"
    assert status["outs/cells.parquet"] == "MISMATCH"
    assert status[v.TIERS["core"][3][1]] == "MISSING"
    assert "3 failed" in v.render(checks)


def test_downloads_only_missing(tmp_path: Path) -> None:
    contents = make_layout(tmp_path)
    missing_supp = v.TIERS["meta"][1][1]
    (tmp_path / missing_supp).unlink()
    (tmp_path / "outs/gene_panel.json").unlink()
    fetched: list[str] = []

    def downloader(url: str, dest: Path) -> None:
        fetched.append(url)
        dest.write_bytes(contents[missing_supp])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("gene_panel.json", b"x" * 150_000)
        zf.writestr("other.bin", b"y" * 1000)
    blob = buf.getvalue()
    ranges: list[tuple[int, int]] = []

    def bundle_fetcher(url: str):
        def fetch(a: int, b: int) -> bytes:
            ranges.append((a, b))
            return blob[a : b + 1]

        return fetch, len(blob)

    urls = v.parse_env((tmp_path / "urls.env").read_text())
    urls["GENE_GROUPS_URL"] = "https://example.invalid/gg"
    (tmp_path / "urls.env").write_text("\n".join(f"{k}={val}" for k, val in urls.items()))
    checks = v.verify(tmp_path, ["meta", "core"], downloader=downloader, bundle_fetcher=bundle_fetcher)
    st = {c.path: c.status for c in checks}
    assert st[missing_supp] == "downloaded" and st["outs/gene_panel.json"] == "downloaded"
    assert fetched == ["https://example.invalid/gg"]
    assert ranges and all(b - a < len(blob) for a, b in ranges)
    assert (tmp_path / "outs/gene_panel.json").read_bytes() == b"x" * 150_000


def test_parsers_and_errors(tmp_path: Path) -> None:
    assert v.parse_members("   8.6 MB  cells.parquet\n    0.0 MB  morphology_focus/\nbad line") == {
        "cells.parquet": 8.6,
        "morphology_focus/": 0.0,
    }
    assert v.size_matches(8_635_427, 8.6) and not v.size_matches(8_735_427, 8.6)
    with pytest.raises(ValueError, match="unknown tier"):
        v.verify(tmp_path, ["nope"])
    assert "meta:" in v.render_tiers() and "boundaries:" in v.render_tiers()
    r = v.RangeReader(lambda a, b: bytes(range(a, b + 1)), 10)
    assert r.readable() and r.seekable()
    r.seek(-3, io.SEEK_END)
    assert r.tell() == 7 and r.read(5) == bytes([7, 8, 9]) and r.read(1) == b""
