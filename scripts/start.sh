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

PORT="${COUNCIL_PORT:-8443}"
HOST="${COUNCIL_HOST:-0.0.0.0}"
# if the port is busy, pick the next free one (common first-run problem)
if [ -n "$( (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; echo ok )" ]; then
  echo "  ⚠ port $PORT is busy - trying the next free port..."
  for p in $(seq $((PORT + 1)) $((PORT + 20))); do
    if ! (exec 3<>/dev/tcp/127.0.0.1/$p) 2>/dev/null; then
      PORT=$p
      break
    fi
  done
fi
echo "  Dashboard: http://localhost:$PORT   (Ctrl+C to stop)"
exec "$ROOT/.venv/bin/python" -m uvicorn council.orchestrator.main:app --host "$HOST" --port "$PORT"
