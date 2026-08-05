.PHONY: venv test

PY := .venv/bin/python
PIP := .venv/bin/pip

.venv/bin/python: requirements-dev.txt pyproject.toml
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

venv: .venv/bin/python

test: .venv/bin/python
	PYTHONPATH=. $(PY) -m pytest -q
