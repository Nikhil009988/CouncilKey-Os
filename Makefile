.PHONY: help version deps lint test clean

IMAGE_REGISTRY ?=
IMAGE_NAMESPACE ?=
IMAGE := councilkey-os
IMAGE_URI ?= localhost/$(IMAGE)
VERSION ?= $(shell cat VERSION 2>/dev/null || echo 1.0.0-dev)
OPENCLAW_REF ?= 2026.7.1
HERMES_REF ?= main
AGENTZERO_REF ?= main

help:
	@echo "CouncilKey-Os Makefile v$(VERSION)"
	@echo ""
	@echo "  deps        Install build deps"
	@echo "  lint        Lint shell + python"
	@echo "  test        Run pytest"
	@echo "  clean       Remove build artifacts"
	@echo "  version     Show version"
	@echo ""
	@echo "  make deps test lint clean version"

version:
	@echo $(VERSION)

deps:
	@echo "Install deps manually per BUILD.md"

lint:
	@echo "Lint..."
	@python -m ruff check council tests scripts || true

test:
	@echo "Run tests..."
	@python -m pytest tests -q

clean:
	@echo "Clean..."
	@rm -rf .venv dist build output tmp .pytest_cache .mypy_cache __pycache__
