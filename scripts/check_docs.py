#!/usr/bin/env python3
"""Phase 0 documentation checks (BRIEF §10).

Stdlib only. Run from the repo root: `uv run python scripts/check_docs.py`.
Exits 0 only if every check passes. Each check prints PASS/FAIL plus details.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BRIEF = DOCS / "BRIEF.md"
PRD = DOCS / "PRD.md"
TECH_SPEC = DOCS / "TECH_SPEC.md"
DATA_CONTRACT = DOCS / "DATA_CONTRACT.md"
TEST_PLAN = DOCS / "TEST_PLAN.md"
ROADMAP = DOCS / "ROADMAP.md"
OPEN_QUESTIONS = DOCS / "OPEN_QUESTIONS.md"
DOMAIN = DOCS / "learn" / "00-domain.md"
PROGRESS = ROOT / "PROGRESS.md"
GOALS = ROOT / "GOALS.md"

DELIVERABLES = [PRD, TECH_SPEC, DATA_CONTRACT, TEST_PLAN, ROADMAP, OPEN_QUESTIONS, DOMAIN, PROGRESS]
ADR_NUMBERS = [f"{n:04d}" for n in range(1, 9)]
# One printed page of prose; tables and headings included.
ADR_MAX_WORDS = 700

ID_RE = re.compile(r"\b(?:US-\d+|FR-[A-Z]\d+|NFR-\d+)\b")
TAG_RE = re.compile(r"\[(PDF|Call|Assumption|Product|Diego)\]")
PRIORITIES = {"M", "S", "C", "W"}
TEST_ID_RE = re.compile(r"\bT-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")

# Calendar dates. The only allowed one is the final deadline (~March 2027).
ALLOWED_DATE_RE = re.compile(r"~?\s*\b(?:Mar(?:ch)?|marzo)\.?\s+2027\b", re.IGNORECASE)
MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|"
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
)
DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # ISO
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),  # 23/09/26
    re.compile(rf"\b(?:{MONTHS})\.?\s+\d{{1,2}}\b", re.IGNORECASE),  # Sep 23
    re.compile(rf"\b\d{{1,2}}\s+(?:de\s+)?(?:{MONTHS})\b", re.IGNORECASE),  # 23 Sep / 23 de septiembre
    re.compile(r"\b(?:19|20)\d{2}\b"),  # any year
    re.compile(r"\b(?:next|this|last)\s+(?:week|month|quarter)\b", re.IGNORECASE),
]


@dataclass
class Result:
    name: str
    ok: bool
    details: list[str] = field(default_factory=list)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def table_rows(text: str) -> list[list[str]]:
    """Markdown table rows as stripped cells (separator rows dropped)."""
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|") or re.fullmatch(r"\|[\s:|-]+\|", s):
            continue
        rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows


def id_rows(text: str) -> dict[str, list[str]]:
    """First table row whose first cell is exactly a requirement ID."""
    out: dict[str, list[str]] = {}
    for row in table_rows(text):
        first = row[0].strip("`* ")
        if ID_RE.fullmatch(first) and first not in out:
            out[first] = row
    return out


def row_priority(row: list[str]) -> str | None:
    for cell in row[1:]:
        if cell.strip("`* ") in PRIORITIES:
            return cell.strip("`* ")
    return None


def row_tags(row: list[str]) -> set[str]:
    return set(TAG_RE.findall(" ".join(row)))


def section(text: str, heading_re: str) -> str:
    """Body of the first markdown section whose heading matches, up to the next heading of same or higher level."""
    m = re.search(rf"^(#+)\s+{heading_re}.*$", text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end() :]
    end = re.search(rf"^#{{1,{level}}}\s", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def brief_ids() -> dict[str, list[str]]:
    return id_rows(read(BRIEF))


# --------------------------------------------------------------------------- checks


def check_deliverables() -> Result:
    missing = [str(p.relative_to(ROOT)) for p in DELIVERABLES if not p.is_file()]
    adrs = {p.name[:4]: p for p in (DOCS / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")}
    missing += [f"docs/adr/{n}-*.md" for n in ADR_NUMBERS if n not in adrs]
    missing += ["scripts/check_docs.py"] if not (ROOT / "scripts" / "check_docs.py").is_file() else []
    return Result(
        "Phase 0 deliverables exist (BRIEF §10)",
        not missing,
        [f"missing: {m}" for m in missing]
        or [f"{len(DELIVERABLES)} documents + ADRs {ADR_NUMBERS[0]}-{ADR_NUMBERS[-1]}"],
    )


def check_brief_unchanged() -> Result:
    proc = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "docs/BRIEF.md"], cwd=ROOT, check=False)
    return Result(
        "docs/BRIEF.md unchanged vs HEAD",
        proc.returncode == 0,
        ["git diff HEAD -- docs/BRIEF.md is empty"] if proc.returncode == 0 else ["BRIEF.md was modified"],
    )


def check_prd_ids() -> Result:
    brief = brief_ids()
    prd_text = read(PRD)
    prd = id_rows(prd_text)
    changelog = section(prd_text, r"Changelog")
    problems, counts = [], {"US": 0, "FR": 0, "NFR": 0}
    for rid, brow in brief.items():
        counts[rid.split("-")[0]] += 1
        row = prd.get(rid)
        if row is None:
            problems.append(f"{rid}: not in a PRD table")
            continue
        p = row_priority(row)
        if p is None:
            problems.append(f"{rid}: no priority (M/S/C/W) in PRD row")
        bp = row_priority(brow)
        if bp and p and bp != p and rid not in changelog:
            problems.append(f"{rid}: priority {bp} in BRIEF vs {p} in PRD without a changelog entry")
        tags, btags = row_tags(row), row_tags(brow)
        if not tags:
            problems.append(f"{rid}: no source tag in PRD row")
        elif tags != btags and rid not in changelog:
            problems.append(
                f"{rid}: source tags {sorted(btags)} in BRIEF vs {sorted(tags)} in PRD without a changelog entry"
            )
    extra = sorted(set(prd) - set(brief))
    details = problems or [
        (
            f"{len(brief)} IDs in BRIEF ({counts['US']} US, {counts['FR']} FR, {counts['NFR']} NFR); "
            "all present in PRD with priority and matching source tags"
        )
    ]
    if extra:
        details.append(f"PRD-only IDs (allowed, must be in changelog): {extra}")
        problems += [f"{e}: PRD-only ID missing from changelog" for e in extra if e not in changelog]
    return Result("Every BRIEF US/FR/NFR ID is in PRD with priority + source tag", not problems, details)


def check_acceptance() -> Result:
    prd_text = read(PRD)
    prd = id_rows(prd_text)
    problems, n_ms, n_ac = [], 0, 0
    for rid, row in prd.items():
        if row_priority(row) not in {"M", "S"}:
            continue
        n_ms += 1
        acs = [ln for ln in prd_text.splitlines() if re.search(rf"\bAC-{re.escape(rid)}\.\d+\b", ln)]
        gwt = [ln for ln in acs if all(re.search(rf"\b{w}\b", ln, re.IGNORECASE) for w in ("given", "when", "then"))]
        n_ac += len(gwt)
        if not gwt:
            problems.append(f"{rid}: no Given/When/Then acceptance criterion (AC-{rid}.N)")
    return Result(
        "Every Must/Should has >= 1 Given/When/Then criterion",
        not problems,
        problems or [f"{n_ms} Must/Should IDs, {n_ac} Given/When/Then criteria"],
    )


def check_traceability() -> Result:
    brief = brief_ids()
    text = read(TEST_PLAN)
    catalog: dict[str, str] = {}
    matrix: dict[str, list[str]] = {}
    for row in table_rows(text):
        first = row[0].strip("`* ")
        if TEST_ID_RE.fullmatch(first) and len(row) >= 2:
            catalog[first] = row[1].strip("`* ").lower()
        elif ID_RE.fullmatch(first):
            matrix.setdefault(first, []).extend(TEST_ID_RE.findall(" ".join(row[1:])))
    problems = []
    for rid in brief:
        tests = matrix.get(rid, [])
        if not tests:
            problems.append(f"{rid}: no test in the traceability matrix")
        undefined = [t for t in tests if t not in catalog]
        if undefined:
            problems.append(f"{rid}: tests not defined in the catalog: {undefined}")
    by_type: dict[str, int] = {}
    for kind in catalog.values():
        by_type[kind] = by_type.get(kind, 0) + 1
    summary = ", ".join(f"{k} {v}" for k, v in sorted(by_type.items()))
    return Result(
        "Every ID maps to >= 1 test in TEST_PLAN",
        not problems,
        problems or [f"{len(brief)} IDs mapped; {len(catalog)} tests in catalog ({summary})"],
    )


def check_dates() -> Result:
    files = (
        [p for p in DELIVERABLES if p.is_file()]
        + sorted((DOCS / "adr").glob("*.md"))
        + sorted((DOCS / "learn").glob("*.md"))
    )
    files = list(dict.fromkeys(files))
    hits, allowed = [], 0
    for path in files:
        for n, line in enumerate(read(path).splitlines(), 1):
            allowed += len(ALLOWED_DATE_RE.findall(line))
            stripped = ALLOWED_DATE_RE.sub(" ", line)
            for pat in DATE_PATTERNS:
                for m in pat.finditer(stripped):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: '{m.group(0)}'")
    return Result(
        "No calendar dates except the final deadline",
        not hits,
        hits or [f"{len(files)} files scanned; only the deadline appears ({allowed} mentions)"],
    )


def check_open_questions() -> Result:
    text = read(OPEN_QUESTIONS)
    rows = table_rows(text)
    header = next((r for r in rows if r and r[0].lower() == "id"), None)
    if header is None:
        return Result("Open questions complete", False, ["no table with an 'ID' header"])
    cols = {
        name: next((i for i, h in enumerate(header) if name in h.lower()), -1)
        for name in ("recipient", "blocks", "status", "default")
    }
    if -1 in cols.values():
        return Result("Open questions complete", False, [f"missing columns: {[k for k, v in cols.items() if v < 0]}"])
    qs = {r[0].strip("`* "): r for r in rows if re.fullmatch(r"Q\d+", r[0].strip("`* "))}
    problems = [f"Q{n}: missing" for n in range(1, 13) if f"Q{n}" not in qs]
    agenda = section(text, r"Meeting agenda")
    deploy = section(text, r"Deployment step")
    subsections = re.findall(r"^###\s+(.*)$", agenda, re.MULTILINE)
    if not subsections or "phase 4" not in subsections[0].lower():
        problems.append("'## Meeting agenda' must exist and its first '###' group must unblock Phase 4")
    first_group = section(agenda, re.escape(subsections[0])) if subsections else ""
    n_open = 0
    for q, r in qs.items():
        if any(i >= len(r) or r[i].strip("`*— -") == "" for i in cols.values()):
            problems += [f"{q}: empty '{n}'" for n, i in cols.items() if i >= len(r) or r[i].strip("`*— -") == ""]
            continue
        if r[cols["status"]].lower().startswith("answered"):
            continue
        n_open += 1
        # Jair's items wait for the deployment step; everything else goes on the meeting agenda.
        who = {w.strip() for w in re.split(r"[/,]", r[cols["recipient"]]) if w.strip()}
        where, body = ("Deployment step", deploy) if who == {"Jair"} else ("Meeting agenda", agenda)
        if not re.search(rf"\b{q}\b", body):
            problems.append(f"{q}: not in '{where}'")
        if (
            where == "Meeting agenda"
            and r[cols["blocks"]].strip().startswith("Phase 4")
            and not re.search(rf"\b{q}\b", first_group)
        ):
            problems.append(f"{q}: blocks Phase 4 but is not in the first agenda group")
    return Result(
        "Every open question has recipient, blocker, status and default; agenda ordered",
        not problems,
        problems
        or [
            (
                f"{len(qs)} questions (Q1-Q{len(qs)}), {n_open} open; meeting agenda groups: "
                f"{' → '.join(h.split('—')[0].strip() for h in subsections)}; "
                "Jair's items under Deployment step"
            )
        ],
    )


def check_adrs() -> Result:
    problems, words = [], {}
    for path in sorted((DOCS / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = read(path)
        name = path.name
        for heading in ("Context", "Options", "Decision", "Consequences"):
            if not re.search(rf"^##\s+{heading}", text, re.MULTILINE):
                problems.append(f"{name}: missing '## {heading}'")
        last = [ln for ln in text.splitlines() if ln.strip()][-1]
        if not last.startswith("**Building block:**"):
            problems.append(f"{name}: last line must be '**Building block:** ...'")
        wc = len(text.split())
        words[name[:4]] = wc
        if wc > ADR_MAX_WORDS:
            problems.append(f"{name}: {wc} words > {ADR_MAX_WORDS} (one page)")
        if name.startswith("0001"):
            for rid in ("FR-T1", "FR-C3", "FR-G6", "NFR-16"):
                if rid not in section(text, "Options"):
                    problems.append(f"{name}: options not compared against {rid}")
            if not re.search(r"^##\s+Decision\s*\n+\s*\*\*", text, re.MULTILINE):
                problems.append(f"{name}: Decision must open with a bold one-line decision")
    return Result(
        "ADRs: sections, one page, building block; 0001 compares FR-T1/FR-C3/FR-G6/NFR-16",
        not problems,
        problems or [f"words per ADR: {words} (max {ADR_MAX_WORDS})"],
    )


def check_sections() -> Result:
    required: dict[Path, list[str]] = {
        PRD: [
            "Problem",
            "Goals",
            "Personas",
            "User stories",
            "Functional requirements",
            "Non-functional requirements",
            "Acceptance criteria",
            "Definition of polish",
            "Success metrics",
            "Risks",
            "Changelog",
        ],
        TECH_SPEC: [
            "Architecture",
            "Pipeline",
            "Asset format",
            "Web architecture",
            "Performance plan",
            "Testing",
            "Deployment",
            "Privacy",
            "Failure modes",
        ],
        DATA_CONTRACT: [
            "cells",
            "genes",
            "expression",
            "clusters",
            "cores",
            "sections",
            "dataset",
            "Adapter interface",
            "Validation",
        ],
        TEST_PLAN: ["Test catalog", "Traceability matrix"],
        PROGRESS: ["Phase", "Done", "Next", "Blockers", "Decisions needed"],
    }
    problems = []
    for path, heads in required.items():
        text = read(path)
        for h in heads:
            if not re.search(rf"^#+\s+.*\b{re.escape(h)}", text, re.MULTILINE | re.IGNORECASE):
                problems.append(f"{path.relative_to(ROOT)}: missing section '{h}'")
    spec = read(TECH_SPEC)
    if "```mermaid" not in spec:
        problems.append("TECH_SPEC.md: no Mermaid architecture diagram")
    if not re.search(r"core[- ]open", section(spec, r"\d*\.?\s*Performance plan"), re.IGNORECASE):
        problems.append("TECH_SPEC.md: performance plan lacks a core-open budget")
    contract = read(DATA_CONTRACT)
    for f in (
        "cell_id",
        "section_id",
        "core_id",
        "patient_id",
        "x_um",
        "y_um",
        "umap_x",
        "umap_y",
        "cluster_id",
        "n_transcripts",
        "gene_id",
        "symbol",
        "panel",
        "label",
        "color",
        "center_um",
        "radius_um",
        "bbox",
        "affine",
        "pixel_size",
        "license",
        "citation",
        "provenance",
        "synthetic",
    ):
        if not re.search(rf"`{f}", contract):
            problems.append(f"DATA_CONTRACT.md: minimum field '{f}' (BRIEF §4.4) not defined")
    domain = read(DOMAIN)
    if len(re.findall(r"\*\*Analogy", domain)) < 8:
        problems.append("learn/00-domain.md: fewer than 8 concepts with an analogy")
    if not re.search(r"^#+\s+.*re-derive", domain, re.MULTILINE | re.IGNORECASE):
        problems.append("learn/00-domain.md: no 're-derive without notes' section")
    return Result(
        "Documents contain the sections BRIEF §10 asks for",
        not problems,
        problems
        or [
            (
                f"{sum(len(v) for v in required.values())} required sections, Mermaid diagram, "
                "core-open budget, 24 contract fields, domain analogies present"
            )
        ],
    )


def check_roadmap() -> Result:
    goals = read(GOALS)
    order = re.findall(r"^\|\s*(\d)\s*\|\s*`(g\d-[a-z-]+)`", goals, re.MULTILINE)
    text = read(ROADMAP)
    problems, positions = [], []
    for phase, goal in order:
        if phase == "0":
            continue
        m = re.search(rf"^##\s+Phase {phase}\b.*`{goal}`.*$", text, re.MULTILINE)
        if not m:
            problems.append(f"Phase {phase}: no '## Phase {phase} ... `{goal}`' heading")
            continue
        positions.append(m.start())
        body = section(text, rf"Phase {phase}\b")
        for part in ("Exit criteria", "Gate"):
            if part.lower() not in body.lower():
                problems.append(f"Phase {phase}: missing '{part}'")
    if positions != sorted(positions):
        problems.append("phases are not in GOALS.md order")
    return Result(
        "ROADMAP follows GOALS.md phase order with exit criteria and gates",
        not problems,
        problems or ["phases " + " → ".join(g for p, g in order if p != "0")],
    )


CHECKS: list[Callable[[], Result]] = [
    check_deliverables,
    check_brief_unchanged,
    check_prd_ids,
    check_acceptance,
    check_traceability,
    check_dates,
    check_open_questions,
    check_adrs,
    check_sections,
    check_roadmap,
]


def main() -> int:
    failed = 0
    for check in CHECKS:
        try:
            r = check()
        except FileNotFoundError as e:
            r = Result(check.__name__, False, [f"file not found: {e.filename}"])
        failed += not r.ok
        print(f"[{'PASS' if r.ok else 'FAIL'}] {r.name}")
        for d in r.details:
            print(f"       {d}")
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
