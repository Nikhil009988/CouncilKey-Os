#!/usr/bin/env bash
# setup.sh - One-command setup for CouncilKey-Os.
#
#   [1] Python environment + CouncilKey-Os
#   [2] INSTALLS EVERYTHING to make the agents run:
#       - all 5 external agents (Hermes, OpenClaw, CrewAI, Aider via their
#         official installers; OpenCode via npm, no Docker)
#       - the API key (from OPENAI_API_KEY / ANTHROPIC / GEMINI / OPENROUTER
#         env, or the interactive wizard)
#       - verifies the council answers
#
# Usage:
#   ./scripts/setup.sh                  # interactive wizard (asks for key + agents)
#   ./scripts/setup.sh --auto           # INSTALL EVERYTHING automatically
#   ./scripts/setup.sh --auto --api-key sk-...   # + key
#   ./scripts/setup.sh --no-agents      # wizard, skip external agents
#   ./scripts/setup.sh --skip-tests     # don't run tests/verify
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AUTO=0
NO_AGENTS=0
SKIP_TESTS=0
API_KEY=""
for arg in "$@"; do
  case "$arg" in
    --auto) AUTO=1 ;;
    --no-agents) NO_AGENTS=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    --api-key) API_KEY="${2:-}"; shift || true ;;
    *) ;;
  esac
done

echo "=============================================="
echo " CouncilKey-Os setup"
echo "=============================================="

# 0. prerequisites with CLEAR messages
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo ""
  echo "❌ Python is not installed or not on PATH."
  echo ""
  echo "   Install it (Linux: sudo apt install python3 python3-venv)"
  echo "   macOS: https://www.python.org/downloads/"
  echo "   Then open a NEW terminal and re-run this setup."
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  echo ""
  echo "❌ git is not installed.  Install it and re-run."
  exit 1
fi

# 1. Python environment + package
echo ""
echo "[1/3] Installing CouncilKey-Os..."
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv" 2>/dev/null || python -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install -q -e "$ROOT[dev]"
echo "      ok - 'councilkey' CLI ready"

# 2a. AUTO: install everything without prompts
if [ "$AUTO" -eq 1 ]; then
  echo ""
  echo "[2/3] Installing ALL agents automatically (this takes a few minutes)..."
  "$ROOT/.venv/bin/councilkey" agents install || true
  echo "      agents installed - check with: councilkey agents status"

  # API key: env vars first, then --api-key
  KEY_ENV=""; PROVIDER="openai"
  if [ -n "${OPENAI_API_KEY:-}" ]; then KEY_ENV="$OPENAI_API_KEY"
  elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then KEY_ENV="$ANTHROPIC_API_KEY"; PROVIDER="anthropic"
  elif [ -n "${GEMINI_API_KEY:-}" ]; then KEY_ENV="$GEMINI_API_KEY"; PROVIDER="gemini"
  elif [ -n "${OPENROUTER_API_KEY:-}" ]; then KEY_ENV="$OPENROUTER_API_KEY"; PROVIDER="openrouter"
  elif [ -n "$API_KEY" ]; then KEY_ENV="$API_KEY"
  fi

  if [ -n "$KEY_ENV" ]; then
    echo ""
    echo "[2/3] Storing the API key (from env / --api-key)..."
    "$ROOT/.venv/bin/councilkey" setup --provider "$PROVIDER" --api-key "$KEY_ENV" \
      --no-agents --skip-tests --skip-verify || true
    echo "      ok - key stored encrypted"
  else
    echo ""
    echo "      ⚠ no API key found (OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / OPENROUTER_API_KEY env, or --api-key)."
    echo "        The agents won't answer until you add one:"
    echo "        ./councilkey setup"
  fi
else
  # 2b. interactive wizard (or non-interactive defaults)
  echo ""
  echo "[2/3] Setup wizard..."
  WIZARD_ARGS=""
  [ "$NO_AGENTS" -eq 1 ] && WIZARD_ARGS="$WIZARD_ARGS --no-agents"
  [ "$SKIP_TESTS" -eq 1 ] && WIZARD_ARGS="$WIZARD_ARGS --skip-tests"
  if [ -t 0 ] && [ -t 1 ]; then
    exec "$ROOT/.venv/bin/councilkey" setup $WIZARD_ARGS
  else
    echo "      non-interactive shell - run 'councilkey setup' anytime"
    "$ROOT/.venv/bin/councilkey" doctor || true
  fi
fi

# 3. verify
if [ "$SKIP_TESTS" -eq 0 ] && [ "$AUTO" -eq 1 ]; then
  echo ""
  echo "[3/3] Verifying the council (real ask)..."
  "$ROOT/.venv/bin/councilkey" agents verify || true
fi

echo ""
echo "=============================================="
echo " ✅ Setup complete"
echo ""
echo "   Start the dashboard:   ./scripts/start.sh"
echo "   Open:                  http://localhost:8443"
echo "   Agent status:          councilkey agents status"
echo "=============================================="
