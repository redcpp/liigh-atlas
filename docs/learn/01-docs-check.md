# 01 — `scripts/check_docs.py`: the Phase 0 document gate

## What it does
Reads `docs/BRIEF.md` as the source of truth and checks that the Phase 0 documents agree with it:
1. every deliverable of BRIEF §10 exists, including ADRs 0001–0008, and BRIEF is unchanged vs `HEAD`;
2. every US/FR/NFR ID in a BRIEF table has a PRD table row with priority and the **same source tags**
   (a changed tag or priority is only accepted if the PRD changelog mentions that ID — this is how
   "never promote an `[Assumption]` to fact" is enforced mechanically);
3. every Must/Should has an `AC-<ID>.N` line containing Given, When and Then;
4. every ID maps to ≥ 1 test in the TEST_PLAN matrix, and every referenced test is in the catalog;
5. no calendar dates in any Phase 0 document except the deadline "~March 2027";
6. every open question has recipient, blocker, status and default, and each open one appears in the
   batched message for its recipient;
7. ADRs have Context/Options/Decision/Consequences, fit one page (≤ 700 words), end with the
   building-block line, and ADR-0001 compares options against FR-T1, FR-C3, FR-G6 and NFR-16;
8. PRD, TECH_SPEC, DATA_CONTRACT, TEST_PLAN and PROGRESS have the sections BRIEF §10 asks for;
9. ROADMAP lists phases 1–6 in `GOALS.md` order, each with exit criteria and a gate.

## Why this design
- Stdlib only, so it runs before `make setup` exists (`uv run python scripts/check_docs.py`).
- It parses the **tables** of BRIEF instead of a hard-coded ID list, so a new requirement in the brief
  immediately fails the check until PRD and TEST_PLAN catch up.
- The date check is deliberately strict (any year, month + day, relative weeks): false positives are
  cheap to reword; a stray date in a plan is the failure mode it guards against.

## How to verify by hand
1. `uv run python scripts/check_docs.py; echo $?` → ten `[PASS]` lines and `0`.
2. Break it on purpose: change `[Assumption]` to `[PDF]` on the FR-G2 row of `docs/PRD.md` → the
   PRD check fails naming FR-G2; revert.
3. Add a month name followed by a day number (a made-up due date) to `PROGRESS.md` → the date check fails with file and line; revert.
4. Delete the T-E2E-C4-01 row from the TEST_PLAN catalog → the traceability check reports FR-C4; revert.
