PYTHON ?= python

.PHONY: install format lint typecheck test migrate seed ingest serve eval research web-build identity storage

install:
	$(PYTHON) -m pip install -e ".[dev,research]"

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

lint:
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest --cov=resolveai --cov-report=term-missing --cov-fail-under=80

migrate:
	$(PYTHON) -m alembic -c apps/api/alembic.ini upgrade head

seed:
	$(PYTHON) -m resolveai.seed

ingest:
	$(PYTHON) scripts/ingest_docs.py docs/PROJECT_SPEC.md

serve:
	$(PYTHON) -m uvicorn resolveai.main:app --reload --host 0.0.0.0 --port 8000

eval:
	$(PYTHON) scripts/run_eval.py datasets/eval/smoke-v1.json

research:
	$(PYTHON) scripts/prepare_banking77.py
	$(PYTHON) scripts/prepare_prompt_injection_dataset.py
	$(PYTHON) scripts/run_banking77_validation.py
	$(PYTHON) scripts/run_guardrail_validation.py
	$(PYTHON) scripts/run_research_benchmark.py
	$(PYTHON) scripts/run_resilience_experiment.py
	$(PYTHON) scripts/run_provider_measurement.py --mode deterministic --sample-size 100
	$(PYTHON) scripts/prepare_human_study.py
	$(PYTHON) scripts/build_google_form_script.py

web-build:
	cd apps/web && npm install && npm run build

identity:
	docker compose --profile identity up -d keycloak

storage:
	docker compose --profile storage up -d seaweedfs
