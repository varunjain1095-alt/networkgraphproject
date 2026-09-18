.PHONY: help install install-phase2 check-env init-db smoke generate validate graphs metrics dashboard pipeline pipeline-full demo check-cache perf-smoke pre-bugs pre-bugs-phase2 train-models eval-phase1 eval-phase2 eval-project test test-integration

PYTHON ?= python

help:
	@echo Network Graph Intelligence — make targets
	@echo.
	@echo   install           pip install Phase 1 requirements
	@echo   install-phase2    pip install Phase 2 requirements
	@echo   check-env         Validate .env and paths
	@echo   init-db           Create empty SQLite schema
	@echo   smoke             Phase 0 smoke test
	@echo   generate          Synthetic data generation (Phase 1A)
	@echo   validate          Data validation (Phase 1A)
	@echo   graphs            Build graph layers (Phase 1B)
	@echo   metrics           Compute NetworkX metrics (Phase 1C)
	@echo   train-models      Train Phase 2 PyG models
	@echo   dashboard         Start Plotly Dash (Phase 1E)
	@echo   pipeline          generate -^> validate -^> graphs -^> metrics
	@echo   pipeline-full     Phase 1 pipeline + train-models + recovery check
	@echo   demo              dev pipeline + dashboard instructions
	@echo   check-cache       Verify cache freshness vs database
	@echo   perf-smoke        Dashboard load time smoke test
	@echo   pre-bugs          Phase 1G automated checklist
	@echo   pre-bugs-phase2   Phase 1G + Phase 2 audits
	@echo   eval-phase1       Phase 1 automated eval gate
	@echo   eval-phase2       Phase 2 automated eval gate
	@echo   eval-project      Full project sign-off (Phase 1 + Phase 2)
	@echo   test              Run unit tests (exclude integration)
	@echo   test-integration  Run integration tests only

install:
	$(PYTHON) -m pip install -r requirements.txt

install-phase2:
	$(PYTHON) -m pip install -r requirements-phase2.txt

check-env:
	$(PYTHON) scripts/check_env.py

init-db:
	$(PYTHON) scripts/init_db.py

smoke:
	$(PYTHON) scripts/smoke_test.py

generate:
	$(PYTHON) generator/run_generator.py

validate:
	$(PYTHON) validator/run_validation.py

graphs:
	$(PYTHON) graphs/builder.py --all-layers

metrics:
	$(PYTHON) analytics/networkx_metrics.py

dashboard:
	$(PYTHON) dashboard/app.py

pipeline:
	$(PYTHON) scripts/run.py pipeline --scale dev

pipeline-full:
	$(PYTHON) scripts/run.py pipeline-full --scale dev

train-models:
	$(PYTHON) scripts/run.py train-models

demo:
	$(PYTHON) scripts/run.py demo

check-cache:
	$(PYTHON) scripts/check_cache_freshness.py

perf-smoke:
	$(PYTHON) scripts/perf_smoke.py

pre-bugs:
	$(PYTHON) scripts/pre_bugs.py --skip-graphs

pre-bugs-phase2:
	$(PYTHON) scripts/pre_bugs.py --phase2 --skip-graphs

eval-phase1:
	$(PYTHON) scripts/run.py eval-phase1 --skip-integration

eval-phase2:
	$(PYTHON) scripts/run.py eval-phase2 --skip-integration --skip-training-tests

eval-project:
	$(PYTHON) scripts/run.py eval-project --skip-integration --skip-training-tests

test:
	$(PYTHON) -m pytest tests/ -m "not integration" -q

test-integration:
	$(PYTHON) -m pytest tests/ -m integration -q
