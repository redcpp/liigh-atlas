"""`make data`: verify the hand-acquired raw files and download only what is missing (T-PIPE-DATA-01).

Supplemental files are checked by md5 (from ``supplemental/md5.expected``, the 10x page values);
``outs/`` members by presence and size against ``members.txt`` (sizes in MB = 10^6 bytes, 0.1 MB
resolution). Missing supplemental files are fetched from ``urls.env``; missing ``outs/`` members are
extracted from the remote bundle with HTTP range requests (the full ZIP is never downloaded).
"""

from __future__ import annotations

import hashlib
import io
import shutil
import urllib.request
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

SUPP_PREFIX = "Xenium_Prime_Ovarian_Cancer_FFPE_XRrun_"

# tier -> list of (kind, relative path, url key or bundle member)
TIERS: dict[str, list[tuple[str, str, str]]] = {
    "meta": [
        ("md5", f"supplemental/{SUPP_PREFIX}cell_groups.csv", "CELL_GROUPS_URL"),
        ("md5", f"supplemental/{SUPP_PREFIX}gene_groups.csv", "GENE_GROUPS_URL"),
        ("md5", f"supplemental/{SUPP_PREFIX}he_imagealignment.csv", "ALIGN_URL"),
        ("md5", f"supplemental/{SUPP_PREFIX}annotation.geojson", "GEOJSON_URL"),
    ],
    "core": [
        ("size", "outs/cells.parquet", "cells.parquet"),
        ("size", "outs/cell_feature_matrix.h5", "cell_feature_matrix.h5"),
        ("size", "outs/analysis.tar.gz", "analysis.tar.gz"),
        ("unpacked", "outs/analysis/umap/gene_expression_2_components/projection.csv", "analysis.tar.gz"),
        ("size", "outs/metrics_summary.csv", "metrics_summary.csv"),
        ("size", "outs/gene_panel.json", "gene_panel.json"),
        ("size", "outs/experiment.xenium", "experiment.xenium"),
        ("size", "outs/analysis_summary.html", "analysis_summary.html"),
    ],
    "he": [("md5", f"supplemental/{SUPP_PREFIX}he_image.ome.tif", "HE_URL")],
    "boundaries": [
        ("size", "outs/cell_boundaries.parquet", "cell_boundaries.parquet"),
        ("size", "outs/nucleus_boundaries.parquet", "nucleus_boundaries.parquet"),
    ],
}


@dataclass
class Check:
    tier: str
    path: str
    method: str
    expected: str
    actual: str
    status: str  # ok | downloaded | MISMATCH | MISSING


def parse_members(text: str) -> dict[str, float]:
    """``members.txt`` lines look like ``   8.6 MB  cells.parquet``."""
    out: dict[str, float] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "MB":
            out[" ".join(parts[2:])] = float(parts[0])
    return out


def parse_md5(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[1]] = parts[0].lower()
    return out


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def md5sum(path: Path, chunk: int = 8 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def size_matches(nbytes: int, expected_mb: float) -> bool:
    return abs(nbytes / 1e6 - expected_mb) <= 0.05 + 1e-9


Fetch = Callable[[int, int], bytes]


class RangeReader(io.RawIOBase):
    """Seekable read-only file over a byte-range fetcher, so ``zipfile`` can read one remote member."""

    def __init__(self, fetch: Fetch, length: int) -> None:
        self._fetch = fetch
        self._length = length
        self._pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self._length}[whence]
        self._pos = max(0, base + offset)
        return self._pos

    def readinto(self, buffer: memoryview) -> int:  # type: ignore[override]
        n = min(len(buffer), self._length - self._pos)
        if n <= 0:
            return 0
        data = self._fetch(self._pos, self._pos + n - 1)
        buffer[: len(data)] = data
        self._pos += len(data)
        return len(data)


def http_fetcher(url: str) -> tuple[Fetch, int]:  # pragma: no cover - network
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req) as resp:
        length = int(resp.headers["Content-Length"])

    def fetch(start: int, end: int) -> bytes:
        r = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(r) as resp:
            data: bytes = resp.read()
            return data

    return fetch, length


def extract_member(fetch: Fetch, length: int, member: str, dest: Path) -> None:
    with zipfile.ZipFile(io.BufferedReader(RangeReader(fetch, length), 1 << 20)) as zf:
        tmp = dest.with_suffix(dest.suffix + ".part")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, tmp.open("wb") as out:
            shutil.copyfileobj(src, out, 8 << 20)
        tmp.replace(dest)


def download(url: str, dest: Path) -> None:  # pragma: no cover - network
    tmp = dest.with_suffix(dest.suffix + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as resp, tmp.open("wb") as out:
        shutil.copyfileobj(resp, out, 8 << 20)
    tmp.replace(dest)


def verify(
    root: Path,
    tiers: Sequence[str],
    *,
    downloader: Callable[[str, Path], None] = download,
    bundle_fetcher: Callable[[str], tuple[Fetch, int]] = http_fetcher,
) -> list[Check]:
    """Verify ``tiers`` under ``root`` (= ``$DATA_ROOT/raw/ovarian-10x``); fetch only what is missing."""
    unknown = [t for t in tiers if t not in TIERS]
    if unknown:
        raise ValueError(f"unknown tier(s): {unknown}; known: {sorted(TIERS)}")
    members = parse_members((root / "members.txt").read_text())
    md5s = parse_md5((root / "supplemental" / "md5.expected").read_text())
    env_file = root / "urls.env"
    urls = parse_env(env_file.read_text()) if env_file.exists() else {}
    checks: list[Check] = []
    for tier in tiers:
        for method, rel, source in TIERS[tier]:
            path = root / rel
            status = "ok"
            if method == "md5":
                expected = md5s[Path(rel).name]
                if not path.exists():
                    downloader(urls[source], path)
                    status = "downloaded"
                actual = md5sum(path)
                if actual != expected:
                    status = "MISMATCH"
            elif method == "size":
                exp_mb = members[source]
                expected = f"{exp_mb:.1f} MB"
                if not path.exists():
                    fetch, length = bundle_fetcher(urls["BUNDLE_URL"])
                    extract_member(fetch, length, source, path)
                    status = "downloaded"
                nbytes = path.stat().st_size
                actual = f"{nbytes / 1e6:.1f} MB"
                if not size_matches(nbytes, exp_mb):
                    status = "MISMATCH"
            else:  # unpacked from an archive member: present and non-empty
                expected = f"present (from {source})"
                if not path.exists() or path.stat().st_size == 0:
                    actual, status = "absent", "MISSING"
                else:
                    actual = f"{path.stat().st_size / 1e6:.1f} MB"
            checks.append(Check(tier, rel, method, expected, actual, status))
    return checks


def render(checks: Sequence[Check]) -> str:
    head = ("tier", "file", "check", "expected", "actual", "status")
    rows = [head] + [(c.tier, c.path, c.method, c.expected, c.actual, c.status) for c in checks]
    widths = [max(len(r[i]) for r in rows) for i in range(len(head))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*r) for r in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    n_dl = sum(c.status == "downloaded" for c in checks)
    n_bad = sum(c.status in ("MISMATCH", "MISSING") for c in checks)
    lines.append(f"{len(checks)} files checked, {n_dl} downloaded, {n_bad} failed")
    return "\n".join(lines)


def render_tiers() -> str:
    lines = []
    for tier, items in TIERS.items():
        lines.append(f"{tier}:")
        lines += [f"  {method:<8} {rel}" for method, rel, _ in items]
    return "\n".join(lines)
