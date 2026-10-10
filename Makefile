.PHONY: setup test run-ci seed serve demo-reset clean

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
EVALFORGE := .venv/bin/evalforge
PYTEST := .venv/bin/pytest

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(PYTHON) scripts/seed.py

test:
	$(PYTEST) -v

run-ci:
	$(EVALFORGE) validate experiments/ci_experiment.yaml
	$(EVALFORGE) run experiments/ci_experiment.yaml
	$(PYTHON) scripts/seed.py
	$(PYTEST) -v

seed:
	$(PYTHON) scripts/seed.py

serve:
	$(EVALFORGE) serve --host 0.0.0.0 --port 8000

demo-reset:
	$(EVALFORGE) demo-reset

clean:
	rm -rf .pytest_cache *.db *.db-wal *.db-shm report_*.html report_*.json test_report.html
