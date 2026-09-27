# CLAUDE.md — Acral Melanoma Spatial Atlas

Public, open-source web atlas for the LIIGH-UNAM acral melanoma Xenium study.
Requirements: `docs/BRIEF.md` (read-only) → `docs/PRD.md` once Phase 0 is approved.
Current state: `PROGRESS.md`. Phase conditions and order: `GOALS.md`.

## Commands
- `make setup` · `make data TIER=list|meta|core|he|boundaries`
- `make pipeline DATASET=ovarian-10x|synthetic-tma|scale|fixture|lab`
- `make dev` · `make test` · `make e2e` · `make bench` · `make figures` · `make verify` · `make build`

## Data locations
- Dev data: `$DATA_ROOT` (external drive). Lab data: `$LAB_DATA_DIR` (encrypted volume). Both outside the repo.
- The internal disk has ~30 GB free: never download the full 10x bundle; follow the tiers in BRIEF §4.2.

## Hard rules
1. Lab data never enters git, CI, logs, screenshots, snapshots or public builds. Print only aggregate counts.
2. No `git push`, no deploys, no external messages. Commit locally on the phase branch.
3. No dates except the final deadline (~Mar 2027, paper submission).
4. Every requirement keeps its source tag; never promote an `[Assumption]` to fact.
5. Static-only architecture: no runtime compute on any server.
6. Deviating from the default stack requires an ADR in `docs/adr/`.
7. Never lower a threshold to make a check pass. Propose the trade-off in `PROGRESS.md`.
8. End every turn: update `PROGRESS.md`, print the verification output relevant to the active goal.

## Conventions
- Python: `uv`, ruff, mypy strict (`pipeline/`), pytest. Deterministic, seeded outputs.
- Web: TypeScript strict, eslint, prettier, vitest, Playwright (chromium/firefox/webkit), axe-core.
- ADR: `docs/adr/NNNN-title.md`, ≤ 1 page, ends with one line naming the system-design building block.
- Conventional commits, small and reviewable.
- Every finished capability adds an entry in `docs/learn/` (what, why this design, how to verify by hand).
