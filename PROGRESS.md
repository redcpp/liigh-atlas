# PROGRESS

Running log. Updated at the end of every agent turn (CLAUDE.md rule 8). No dates except the final
deadline (~March 2027).

## Phase

**Phase 0 — documents before code** (goal `g0-docs`, branch `phase-0-docs`). Gate 0 decisions applied;
`scripts/check_docs.py` green. Phase 1 not started (on hold until the maintainer starts `g1-pipeline`).

## Done

- Phase 0 deliverables: PRD, TECH_SPEC, DATA_CONTRACT, ADRs 0001–0008, TEST_PLAN, ROADMAP,
  OPEN_QUESTIONS, `docs/learn/00-domain.md`, `docs/learn/01-docs-check.md`, `scripts/check_docs.py`.
- **Gate 0 applied** (`[Diego]`):
  1. ADR-0002 accepted with conditions: per-section spatial and per-axis UMAP quantization with
     offset + scale in the manifest; T-PIPE-QUANT-01 asserts ≤ 0.5 µm and ≤ 0.1% of UMAP range; URLs and
     exports use physical units only (ADR-0005 updated: lasso vertices and camera in µm / UMAP units;
     new T-WEB-URL-03; AC-FR-G7.1 requires physical-unit labels).
  2. ADR-0004 accepted with conditions: Lanczos resampling at ≤ source pixel size; manifest keeps the
     source affine (`affine_source` in DATA_CONTRACT) and source pixel size; new T-PIPE-ALIGN-02 runs
     the alignment test on the pre-aligned pyramid. The H&E pyramid build moved from Phase 3 to Phase 1.
  3. User stories stay M; NFR-9 M → S (PRD changelog 0.2).
  4. Dev UMAP: kNN cluster-coherence (15 neighbours) on the provided vs a seeded scanpy UMAP; higher
     wins; recompute cached under `$DATA_ROOT/derived/` with parameters and hash. Added to TECH_SPEC §2,
     DATA_CONTRACT provenance, T-PIPE-UMAP-01 and Phase 1 exit criterion 9.
  5. Nothing sent to the lab. OPEN_QUESTIONS now has a "Meeting agenda" (Phase 4 group first) for the
     in-person meeting after Phase 3, and a "Deployment step — Jair" list (Q8, Q13) for Phase 6.
     Q5's blocker reworded to "public lab build" (Phase 4 itself runs privately under the default).
  `check_docs.py` now enforces the agenda: Jair's open items under Deployment step, every other open
  item on the agenda, and every open item that blocks Phase 4 in the first group.

## Next

1. Maintainer starts Phase 1 (`g1-pipeline`) when ready; exit criteria in `docs/ROADMAP.md` now include
   T-PIPE-ALIGN-02, T-PIPE-QUANT-01 and T-PIPE-UMAP-01 beyond the goal text in `GOALS.md`.
2. Questions stay held: lab agenda at the in-person meeting after Phase 3; Jair's at deployment.

## Blockers

- None for Phase 1. Phase 4 waits on the lab handoff (meeting agenda group 1). Deployment details wait
  on Jair (Q8 confirmation, Q13). A public repo/demo waits on Dany (Q10).

## Decisions needed

1. **ADR-0001** (build a custom React + deck.gl app; no Vitessce, no Viv): still *Proposed*; Gate 0 did
   not mention it. Accept?
2. **ADR-0008** (public tool + private overlay; repo private until Q10): still *Proposed*. Accept?
3. ADR-0003, ADR-0005, ADR-0006, ADR-0007 remain *Proposed*; ADR-0005 was edited only to apply the
   Gate 0 physical-units condition.
4. `GOALS.md` g1 text does not mention the Gate 0 additions (pyramid alignment test, quantization test,
   UMAP selection). ROADMAP carries them; update the goal text too if the evaluator should check them.

## Verification (last run)

See the transcript of this turn: `uv run python scripts/check_docs.py` (exit 0).
