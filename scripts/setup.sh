#!/usr/bin/env bash
# setup.sh - One-command setup for CouncilKey-Os. Does everything:
#   1. creates the Python environment + installs CouncilKey-Os
#   2. DOWNLOADS the 3 agents (Hermes, OpenClaw, Agent Zero)
#   3. installs Ollama (local LLM) and pulls a model, so the 3 agents
#      genuinely answer - no API keys, no cloud
#   4. runs the test suite
#   5. shows the final status
#
# Usage:
#   ./scripts/setup.sh                 # full setup (agents + local LLM)
#   ./scripts/setup.sh --skip-agents   # only the orchestrator itself
#   ./scripts/setup.sh --no-llm        # agents, but no Ollama/model download
#   ./scripts/setup.sh --skip-tests    # don't run pytest at the end
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKIP_AGENTS=0
NO_LLM=0
SKIP_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --skip-agents) SKIP_AGENTS=1 ;;
    --no-llm)      NO_LLM=1 ;;
    --skip-tests)  SKIP_TESTS=1 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

echo "=============================================="
echo " CouncilKey-Os setup"
echo "=============================================="

# 1. Python environment + package
echo ""
echo "[1/5] Installing CouncilKey-Os (Python environment)..."
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install -q -e "$ROOT[dev]"
echo "      ok - 'councilkey' CLI ready"

# 2. Download the 3 agents
if [ "$SKIP_AGENTS" -eq 1 ]; then
  echo "[2/5] Skipping agent download (--skip-agents)"
else
  echo "[2/5] Downloading the 3 agents (Hermes, OpenClaw, Agent Zero)..."
  echo "      This downloads their official repos - can take a few minutes"
  echo "      on the first run (needs an internet connection + git)."
  "$ROOT/.venv/bin/councilkey" agents install || {
    echo ""
    echo "      ⚠ agent download incomplete."
    echo "        - no internet? retry later with:  councilkey agents install"
    echo "        - the council still works via local LLM (next step) even"
    echo "          before the external agents are ready."
  }
fi

# 3. Local LLM (Ollama + model) - makes the 3 agents really answer
if [ "$NO_LLM" -eq 1 ]; then
  echo "[3/5] Skipping local LLM setup (--no-llm)"
else
  echo "[3/5] Setting up the local LLM (Ollama)..."
  if "$ROOT/.venv/bin/councilkey" llm status >/dev/null 2>&1; then
    echo "      ollama already running"
  else
    echo "      installing ollama (one-time, ~100MB)..."
    "$ROOT/.venv/bin/councilkey" llm install || {
      echo "      ⚠ could not install ollama automatically."
      echo "        install it manually from https://ollama.com/download,"
      echo "        then run: councilkey llm pull"
    }
  fi
  echo "      pulling model qwen2.5:3b (~1.9GB, one-time)..."
  "$ROOT/.venv/bin/councilkey" llm pull qwen2.5:3b || {
    echo "      ⚠ model pull failed (check ollama is running: councilkey llm status)"
  }
fi

# 4. Tests
if [ "$SKIP_TESTS" -eq 1 ]; then
  echo "[4/5] Skipping tests (--skip-tests)"
else
  echo "[4/5] Running the test suite..."
  (cd "$ROOT" && "$ROOT/.venv/bin/python" -m pytest tests -q) || true
fi

# 5. Final status - real verification
echo ""
echo "[5/5] Verifying the council..."
"$ROOT/.venv/bin/councilkey" agents verify || true

echo ""
echo "=============================================="
echo " ✅ Setup complete"
echo ""
echo "   Start the dashboard + API:   ./scripts/start.sh"
echo "                                (or: .venv/bin/councilkey serve)"
echo "   Open:                        http://localhost:8443"
echo "   Check agents:                .venv/bin/councilkey agents status"
echo "   Check LLM:                   .venv/bin/councilkey llm status"
echo "=============================================="
