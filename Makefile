.PHONY: help version deps lint test clean

IMAGE_REGISTRY ?=
IMAGE_NAMESPACE ?=
IMAGE := councilkey-os
IMAGE_URI ?= localhost/$(IMAGE)
VERSION ?= $(shell cat VERSION 2>/dev/null || echo 1.0.0-dev)
OPENCLAW_REF ?= 2026.7.1
HERMES_REF ?= main
AGENTZERO_REF ?= main

# Prefer the project venv when it exists, fall back to system python
PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

help:
	@echo "CouncilKey-Os Makefile v$(VERSION)"
	@echo ""
	@echo "  deps        Install the project + dev dependencies"
	@echo "  lint        Lint python (ruff)"
	@echo "  test        Run pytest"
	@echo "  clean       Remove build artifacts"
	@echo "  version     Show version"
	@echo ""
	@echo "  make deps test lint clean version"

version:
	@echo $(VERSION)

deps:
	@echo "Installing project + dev dependencies..."
	@if [ ! -d .venv ]; then python3 -m venv .venv; fi
	@.venv/bin/pip install -q -e ".[dev]"
	@echo "ok - run 'make test' and 'make lint'"

lint:
	@echo "Lint..."
	@$(PY) -m ruff check council tests scripts || true

test:
	@echo "Run tests..."
	@$(PY) -m pytest tests -q

clean:
	@echo "Clean..."
	@rm -rf .venv dist build output tmp .pytest_cache .mypy_cache .ruff_cache __pycache__
