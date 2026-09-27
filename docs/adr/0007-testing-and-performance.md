# ADR-0007 — Testing and performance-measurement strategy

Status: Proposed (maintainer gate after Phase 0)

## Context

Every M/S ID needs an automated test (NFR-15), budgets are acceptance criteria (NFR-3/4/5, TECH_SPEC
§7), and the goal evaluator only reads printed output. Lab data may never appear in snapshots, logs or
CI. Full-scale runs are local on a laptop with data on a spinning USB disk.

## Options

1. Manual QA + a few unit tests: cheap now, unverifiable later.
2. **Test pyramid with requirement tags**: unit (pytest, vitest) → contract/integration → Playwright
   e2e on three engines → bench + Lighthouse + axe, with every test titled by its test ID and
   requirement IDs so traceability is checkable by script.
3. Visual regression on everything: brittle across engines and GPUs; reserved for a few views.

## Decision

**Option 2, with targeted visual tests.**

| Layer | Tool | Scope | Where it runs |
|---|---|---|---|
| Unit (pipeline) | pytest + coverage (≥ 85%) + hypothesis for codecs | adapters, validation, quantization, ordering, encoders | CI (`fixture`), local |
| Contract | pandera schemas on every dataset | DATA_CONTRACT invariants and known totals | every pipeline run |
| Reproducibility | double build, compare manifests | NFR-14 | local (`ovarian-10x`), CI (`fixture`) |
| Unit (web) | vitest (≥ 80% on `state/`, `data/`) | URL codec, migrations, decoders, LRU, color | CI |
| E2E | Playwright chromium/firefox/webkit, `@ID` tags in titles | all M/S stories and FRs | CI (`fixture`), local (`scale`) |
| A11y | `@axe-core/playwright` per view, keyboard-only journeys | NFR-10 | CI |
| Hygiene | fixture failing a test on any `console.error`/`pageerror` | NFR-12 | every e2e test |
| Visual | screenshot diff on `fixture` only (chromium) + alignment overlay test | FR-C1, FR-C5, exports | CI |
| Bench | Playwright + `performance.mark`; rAF frame timing; network byte sum | NFR-3/4/5, TECH_SPEC §7 | local, `scale`, recorded in `docs/perf.md` |
| Lighthouse | Lighthouse CI desktop preset | NFR-11 | local + CI on `fixture` |

**Measurement rules:**
- Bytes: sum of encoded response sizes from Playwright `response` events (CDP `encodedDataLength`
  in chromium) until the app emits the `atlas:interactive` mark.
- Latency: app-emitted marks (`gene:select` → `gene:painted`, after the next `requestAnimationFrame`),
  so the same numbers are available in all three engines; p95 over ≥ 50 samples.
- FPS: median of instantaneous rates from rAF timestamps over a 10 s scripted pan/zoom, after a 2 s
  warm-up; GPU and laptop model recorded in `docs/perf.md` with the disk type.
- A `make bench` run does one warm-up pass when `$DATA_ROOT` is on a spinning disk (BRIEF §9).
- Budgets live in one file (`bench/budgets.json`) copied from TECH_SPEC §7; `make verify` fails when a
  measurement exceeds it. Thresholds change only through `PROGRESS.md` → Decisions needed.

**Privacy:** snapshots, traces and videos are produced only for `fixture`, `synthetic-tma` and `scale`;
the Playwright config refuses `DATASET=lab` for screenshot/video capture. Lab runs print aggregates.

**Traceability:** `docs/TEST_PLAN.md` maps IDs → test IDs; from Phase 1, a script checks every test ID in
the plan exists in the code (`T-…` in the test title) and vice versa.

## Consequences

- Test IDs are part of test names; renaming a test means updating TEST_PLAN (checked).
- Perf numbers are laptop-specific; they are comparable across phases because the reference machine
  and method are fixed.

**Building block:** observability — metrics, SLO-style budgets and automated regression gates.
