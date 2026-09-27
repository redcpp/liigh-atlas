# Acral Melanoma Spatial Atlas — one entry point per task (BRIEF §9).
SHELL := /bin/bash
DATASET ?= fixture
TIER ?= meta,core,he
UV := uv run --frozen
PY := $(UV) python -W ignore::FutureWarning -m atlas_pipeline

.PHONY: setup data pipeline fixture repro dev test test-data lint typecheck e2e bench figures verify build check-repo

setup:            ## install Python (uv) and web (npm) dependencies, enable the git guard hook
	uv sync --frozen
	npm ci --prefix web --no-audit --no-fund
	git config core.hooksPath .githooks
	@echo "setup OK"

data:             ## verify raw tiers under $$DATA_ROOT (TIER=list|meta|core|he|boundaries, comma-separated)
	$(PY) data --tier $(TIER)

pipeline:         ## DATASET=ovarian-10x|synthetic-tma|scale|fixture
	$(PY) run $(DATASET)

repro:            ## run the pipeline twice and compare every asset hash (T-PIPE-REPRO-01)
	$(PY) repro $(DATASET)

fixture:          ## regenerate fixtures/fixture from ovarian-10x (needs $$DATA_ROOT)
	$(PY) make-fixture

test:             ## pipeline tests with coverage (data-marked tests run when $$DATA_ROOT is mounted) + web unit tests
	$(UV) pytest --cov=atlas_pipeline --cov-report=term --cov-fail-under=85
	npm test --prefix web

lint:
	$(UV) ruff check pipeline scripts
	$(UV) ruff format --check pipeline scripts
	npm run lint --prefix web

typecheck:
	$(UV) mypy
	npm run typecheck --prefix web

check-repo:       ## T-REPO: no data files or files > 5 MB tracked outside fixtures/
	$(UV) python scripts/check_repo.py

dev:
	npm run dev --prefix web

e2e bench figures build:
	@echo "make $@: not implemented yet (see docs/ROADMAP.md: e2e/bench Phase 2, figures Phase 5, build Phase 6)"; exit 2

verify: lint typecheck test check-repo   ## grows with e2e + bench + budgets in Phase 2
	@echo "verify OK"
