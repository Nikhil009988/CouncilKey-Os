#!/usr/bin/env bash
# setup.sh - One-command setup for CouncilKey-Os.
#
#   [1] Python environment + CouncilKey-Os
#   [2] LOCAL LLM (Ollama + qwen2.5:3b) -> the council really answers
#       (real local inference, offline, no API keys, no demo)
#   [3] OPTIONAL: the 3 external agents (Hermes, OpenClaw, Agent Zero),
#       each installed with its own official installer
#   [4] test suite
#   [5] verify the council with a real ask
#
# Usage:
#   ./scripts/setup.sh                # everything (recommended)
#   ./scripts/setup.sh --no-agents    # council + local LLM only
#   ./scripts/setup.sh --no-llm       # council + external agents only
#   ./scripts/setup.sh --skip-tests   # don't run pytest at the end
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NO_AGENTS=0
NO_LLM=0
SKIP_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --no-agents) NO_AGENTS=1 ;;
    --no-llm)    NO_LLM=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

echo "=============================================="
echo " CouncilKey-Os setup"
echo "=============================================="

# 1. Python environment + package
echo ""
echo "[1/5] Installing CouncilKey-Os..."
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install -q -e "$ROOT[dev]"
echo "      ok - 'councilkey' CLI ready"

# 2. Local LLM - makes the council REALLY answer
if [ "$NO_LLM" -eq 1 ]; then
  echo "[2/5] Skipping local LLM (--no-llm)"
else
  echo "[2/5] Local LLM (Ollama + qwen2.5:3b) - this makes the 3 agents answer"
  if "$ROOT/.venv/bin/councilkey" llm status >/dev/null 2>&1; then
    echo "      ollama already running"
  else
    echo "      installing ollama (one-time)..."
    "$ROOT/.venv/bin/councilkey" llm install || {
      echo "      ⚠ could not install ollama automatically."
      echo "        install it from https://ollama.com/download, then run:"
      echo "        councilkey llm pull"
    }
  fi
  echo "      pulling model qwen2.5:3b (~1.9GB, one-time)..."
  "$ROOT/.venv/bin/councilkey" llm pull qwen2.5:3b || {
    echo "      ⚠ model pull failed - check: councilkey llm status"
  }
fi

# 3. Optional: external agents via their official installers
if [ "$NO_AGENTS" -eq 1 ]; then
  echo "[3/5] Skipping external agents (--no-agents)"
else
  echo "[3/5] External agents (optional, interactive tools - official installers)"
  echo "      Hermes/OpenClaw/Agent Zero are interactive chat agents with their"
  echo "      own UIs. The council works without them (local LLM above)."
  "$ROOT/.venv/bin/councilkey" agents install || true
fi

# 4. Tests
if [ "$SKIP_TESTS" -eq 1 ]; then
  echo "[4/5] Skipping tests (--skip-tests)"
else
  echo "[4/5] Running the test suite..."
  (cd "$ROOT" && "$ROOT/.venv/bin/python" -m pytest tests -q) || true
fi

# 5. Verify - real ask
echo ""
echo "[5/5] Verifying the council (real ask)..."
"$ROOT/.venv/bin/councilkey" agents verify || true

echo ""
echo "=============================================="
echo " ✅ Setup complete"
echo ""
echo "   Start the dashboard:   ./scripts/start.sh"
echo "   Open:                  http://localhost:8443"
echo "   Agents status:         councilkey agents status"
echo "   LLM status:            councilkey llm status"
echo "=============================================="
