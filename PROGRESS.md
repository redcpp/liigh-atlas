# PROGRESS

Running log. Updated at the end of every agent turn (CLAUDE.md rule 8). No dates except the final
deadline (~March 2027).

## Phase

**Phase 0 — documents before code** (goal `g0-docs`, branch `phase-0-docs`). Status: deliverables
complete and `scripts/check_docs.py` green; waiting for the maintainer gate (review PRD, TECH_SPEC,
ADR-0001, ADR-0008).

## Done

- `docs/PRD.md`: problem, goals/non-goals, personas, 5 stories + 32 FRs + 16 NFRs with priority and
  source tags unchanged from BRIEF, Given/When/Then for every Must/Should, definition of polish, success
  metrics, risks, changelog.
- `docs/TECH_SPEC.md`: Mermaid architecture, pipeline stages, asset format table with sizes, web
  modules/state/render layers, linked views, color, per-interaction budgets (incl. core open < 1.0 s
  p95, ≤ 2 MB), testing, deployment, privacy, failure modes.
- `docs/DATA_CONTRACT.md`: 7 canonical entities with types, units, invariants; validation; adapter
  interface; source mapping for `ovarian-10x`.
- `docs/adr/0001`–`0008`: build custom React + deck.gl (no Vitessce/Viv); typed binaries with uint16
  quantized coordinates; per-gene sparse/dense uint8 files; H&E warped to µm frame as WebP pyramid;
  Zustand + versioned query-param URLs pinned to data release; LIIGH nginx hosting; test pyramid with
  requirement-tagged tests; public tool + private overlay (repo private until Q10).
- `docs/TEST_PLAN.md`: 87-test catalog and traceability matrix for all 53 IDs.
- `docs/ROADMAP.md`: Phases 1–6 in `GOALS.md` order with exit criteria and gates.
- `docs/OPEN_QUESTIONS.md`: Q1–Q16 with recipient, blocker, status, default; one batched message per
  recipient (Estef, Dany, Jair) in Spanish.
- `docs/learn/00-domain.md` (13 concepts with analogies + re-derivation list) and
  `docs/learn/01-docs-check.md`.
- `scripts/check_docs.py` (stdlib only), the only code in the repo.
- Read-only inspection of dev metadata on `$DATA_ROOT` (no download): 407,124 cells; 5,101 gene
  features; 18 cell groups (17 + Unassigned); tissue 11,481 × 7,979 µm; alignment affine rotates ~90°,
  scale ≈ 1.29; 80.5M non-zero matrix entries.

## Next

1. Maintainer gate: review PRD, TECH_SPEC, ADR-0001 (build vs adopt) and ADR-0008 (public vs private);
   approve or edit (ADR status Proposed → Accepted).
2. Send the three batched messages in `docs/OPEN_QUESTIONS.md` (maintainer; the agent contacts no one).
3. Phase 1 (`g1-pipeline`): scaffolding, `make setup`, `make data`, adapters, validation, assets,
   alignment test.

## Blockers

- None for Phase 1. Phase 4 is blocked on the lab handoff (Q1–Q5, Q12, Q14, Q15). Deployment details
  wait on Jair (Q8 confirmation, Q13). Public repo/demo waits on Dany (Q10).

## Decisions needed

1. **ADR-0001:** build custom React + deck.gl app; no Vitessce, no Viv. Approve?
2. **ADR-0002 deviation from the BRIEF default:** uint16-quantized coordinates instead of float32
   (UMAP 3.54 → 1.77 MB at 443K cells) to leave NFR-3 headroom. Approve?
3. **ADR-0004:** warp the H&E into the µm frame offline (one bilinear resampling) instead of applying the
   affine at render time. Approve?
4. **PRD:** NFRs and user stories set to priority M (BRIEF gives them none). Approve?
5. **ADR-0008:** keep the repo private until Q10, with the public/private split already enforced.
6. **UMAP for dev data:** use the Xenium onboard UMAP as provided (clusters come from 10x's Seurat run,
   so UMAP and colors come from different analyses); recompute with scanpy is a config flag. Default: as
   provided.

## Verification (last run)

See the transcript of this turn: `uv run python scripts/check_docs.py` (exit 0), `ls docs docs/adr
docs/learn`, `git diff --stat docs/BRIEF.md` (empty).
