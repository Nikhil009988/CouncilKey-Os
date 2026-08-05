#!/usr/bin/env bash
set -euo pipefail

COUNCIL_HOME="${COUNCIL_HOME:-/var/lib/council}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -e "$ROOT[dev]" -q
fi

exec "$ROOT/.venv/bin/python" -m uvicorn council.orchestrator.main:app --host "${COUNCIL_HOST:-0.0.0.0}" --port "${COUNCIL_PORT:-8443}"
