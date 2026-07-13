.PHONY: help setup run seed clean fresh check test

PYTHON  ?= python3
VENV    ?= .venv
PIP     := $(VENV)/bin/pip
PY      := $(VENV)/bin/python
UVICORN := $(VENV)/bin/uvicorn
PORT    ?= 8000

help:
	@echo "AI Consulting Firm — make targets"
	@echo ""
	@echo "  make setup    create venv, install deps, copy .env.example -> .env, seed DB"
	@echo "  make run      start the FastAPI server (PORT=$(PORT), override with PORT=...)"
	@echo "  make seed     re-seed the agents table (idempotent)"
	@echo "  make check    quick import check (catches syntax errors before run)"
	@echo "  make test     run the smoke test suite (tests/, no Claude API calls)"
	@echo "  make clean    delete the SQLite DB"
	@echo "  make fresh    clean + setup"

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

setup: $(VENV)/bin/activate
	@if [ ! -f .env ]; then \
	  cp .env.example .env; \
	  echo ""; \
	  echo ">>> Created .env from .env.example."; \
	  echo ">>> Edit .env and set ANTHROPIC_API_KEY before running."; \
	  echo ""; \
	fi
	$(PY) seed.py

run:
	$(UVICORN) app.main:app --reload --port $(PORT)

seed:
	$(PY) seed.py

check:
	$(PY) -c "from app import main; print('OK — imports clean.')"

test:
	$(PY) -m pytest tests/ -q

clean:
	rm -f data/app.db data/app.db-journal

fresh: clean setup
