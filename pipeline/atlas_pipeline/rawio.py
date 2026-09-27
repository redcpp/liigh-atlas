"""Open-guard and raw-file log (TECH_SPEC §2 stage 1, T-PIPE-GUARD-01).

Every raw file an adapter reads goes through :func:`use`, which refuses the formats the pipeline must
never read and records the path so the run can print the full list.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

FORBIDDEN_PATTERNS: tuple[str, ...] = ("transcripts.*", "morphology*", "*.zarr.zip")


class ForbiddenRawFileError(PermissionError):
    """The pipeline tried to open a file it must never read."""


def is_forbidden(path: Path) -> bool:
    parts = path.parts
    return any(fnmatch.fnmatch(part, pat) for part in parts for pat in FORBIDDEN_PATTERNS)


@dataclass
class RawFileLog:
    opened: list[tuple[str, str]] = field(default_factory=list)

    def use(self, path: Path, kind: str = "raw") -> Path:
        """Check ``path`` against the guard, log it once and return it."""
        if is_forbidden(path):
            raise ForbiddenRawFileError(f"refusing to open forbidden raw file: {path}")
        entry = (kind, str(path))
        if entry not in self.opened:
            self.opened.append(entry)
        return path

    def forbidden_opened(self) -> list[str]:
        return [p for _, p in self.opened if is_forbidden(Path(p))]

    def render(self) -> str:
        lines = [f"Files opened ({len(self.opened)}):"]
        lines += [f"  [{kind}] {p}" for kind, p in self.opened]
        bad = self.forbidden_opened()
        lines.append("  forbidden (transcripts.*, morphology*, *.zarr.zip): " + ("NONE" if not bad else ", ".join(bad)))
        return "\n".join(lines)
