#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COUNCIL_HOME="${COUNCIL_HOME:-/var/lib/council}"

# Fall back to a repo-local home when the system dir is not writable
# (e.g. running from a plain clone without root privileges).
if ! mkdir -p "$COUNCIL_HOME" 2>/dev/null; then
  COUNCIL_HOME="$ROOT/.council-home"
  mkdir -p "$COUNCIL_HOME"
  echo "note: using repo-local council home: $COUNCIL_HOME"
fi
export COUNCIL_HOME

if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -e "$ROOT[dev]" -q
fi

# Optional: auto-start the 3 agents before serving (COUNCIL_START_AGENTS=1)
if [ "${COUNCIL_START_AGENTS:-0}" = "1" ] && [ -x "$ROOT/.venv/bin/councilkey" ]; then
  "$ROOT/.venv/bin/councilkey" agents start || true
fi

exec "$ROOT/.venv/bin/python" -m uvicorn council.orchestrator.main:app \
  --host "${COUNCIL_HOST:-0.0.0.0}" --port "${COUNCIL_PORT:-8443}"
