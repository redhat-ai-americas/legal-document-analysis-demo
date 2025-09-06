PY=python3
PIP=pip
VENV=.venv
APP=legal-document-analysis

.PHONY: venv install test ui lint clean run batch analyze verify

venv:
	$(PY) -m venv $(VENV)
	. $(VENV)/bin/activate && $(PIP) install -U pip
	. $(VENV)/bin/activate && $(PIP) install -r requirements.txt

install: venv

test:
	. $(VENV)/bin/activate && pytest -q

ui:
	./start_ui.sh

run:
	. $(VENV)/bin/activate && $(PY) scripts/main.py

batch:
	. $(VENV)/bin/activate && $(PY) scripts/batch_process.py

analyze:
	. $(VENV)/bin/activate && $(PY) scripts/analyze_run.py

verify:
	. $(VENV)/bin/activate && $(PY) scripts/verify_reference_fix.py

lint:
	. $(VENV)/bin/activate && ruff check . || true

clean:
	rm -rf $(VENV) __pycache__ */__pycache__ .pytest_cache
