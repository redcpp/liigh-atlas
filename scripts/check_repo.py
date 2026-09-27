"""Repository guard (BRIEF §9, NFR-8): no data extensions or files > 5 MB tracked outside fixtures/.

Used by the pre-commit hook (``--staged``) and by ``make check-repo`` (all tracked files).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DATA_EXT = (".h5ad", ".rds", ".h5", ".parquet", ".zarr", ".tif", ".tiff", ".ome.tif", ".npz", ".zip")
MAX_BYTES = 5 * 1024 * 1024
ALLOWED_PREFIX = "fixtures/"


def violations(paths: list[str], root: Path) -> list[str]:
    bad = []
    for p in paths:
        if p.startswith(ALLOWED_PREFIX):
            f = root / p
            if f.exists() and f.stat().st_size > MAX_BYTES:
                bad.append(f"{p}: {f.stat().st_size} B > 5 MB (fixtures too)")
            continue
        low = p.lower()
        if low.endswith(DATA_EXT) or "/.zarr/" in low:
            bad.append(f"{p}: data file outside fixtures/")
        f = root / p
        if f.exists() and f.stat().st_size > MAX_BYTES:
            bad.append(f"{p}: {f.stat().st_size} B > 5 MB")
    return bad


def main(argv: list[str]) -> int:
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    cmd = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if "--staged" in argv else ["git", "ls-files"]
    )
    paths = subprocess.check_output(cmd, text=True, cwd=root).split()
    bad = violations(paths, root)
    fixture_bytes = sum(
        (root / p).stat().st_size for p in paths if p.startswith(ALLOWED_PREFIX) and (root / p).exists()
    )
    print(f"checked {len(paths)} files; fixtures/ total {fixture_bytes / 1e6:.2f} MB; violations: {len(bad)}")
    for b in bad:
        print("  " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
