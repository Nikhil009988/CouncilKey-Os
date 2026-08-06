#!/usr/bin/env bash
# setup.sh - One-command setup for CouncilKey-Os.
#
#   [1] Python environment + CouncilKey-Os
#   [2] INTERACTIVE WIZARD (councilkey setup):
#       - local LLM (Ollama + qwen2.5:3b) -> the council really answers
#       - model provider + API keys (local Ollama free, or OpenAI/Anthropic/
#         Gemini/OpenRouter) - keys stored in the encrypted vault
#       - optional external agents (Hermes/OpenClaw/Agent Zero) via their
#         official installers
#       - tests + verify
#
# Usage:
#   ./scripts/setup.sh                # interactive wizard (recommended)
#   ./scripts/setup.sh --no-agents    # wizard, skip external agents
#   ./scripts/setup.sh --no-llm       # wizard, skip the local LLM
#   ./scripts/setup.sh --skip-tests   # wizard, don't run pytest
#   echo "y\n1\nn" | ./scripts/setup.sh   # non-interactive -> defaults
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

# 1. Python environment + package (always needed for the wizard too)
echo ""
echo "[1/2] Installing CouncilKey-Os..."
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install -q -e "$ROOT[dev]"
echo "      ok - 'councilkey' CLI ready"

# 2. Interactive wizard (asks: local LLM, provider + API keys, external agents)
WIZARD_ARGS=""
[ "$NO_AGENTS" -eq 1 ] && WIZARD_ARGS="$WIZARD_ARGS --no-agents"
[ "$NO_LLM" -eq 1 ] && WIZARD_ARGS="$WIZARD_ARGS --no-llm"
[ "$SKIP_TESTS" -eq 1 ] && WIZARD_ARGS="$WIZARD_ARGS --skip-tests"

if [ -t 0 ] && [ -t 1 ]; then
  # interactive terminal -> guided wizard with prompts (API keys etc.)
  exec "$ROOT/.venv/bin/councilkey" setup $WIZARD_ARGS
else
  # non-interactive (CI/pipes) -> default flags (local Ollama, no external agents)
  echo "[2/2] Non-interactive mode - running setup with defaults (local Ollama, no external agents)"
  "$ROOT/.venv/bin/councilkey" setup --provider ollama $WIZARD_ARGS
fi
