#!/usr/bin/env bash
# setup.sh - One-command setup for CouncilKey-Os.
#
#   [1] Python environment + CouncilKey-Os
#   [2] INTERACTIVE WIZARD (councilkey setup):
#       - model provider + API key (OpenAI/Anthropic/Gemini/OpenRouter) -
#         stored encrypted in the secrets vault, used by the 3 council roles
#         AND the external agents
#       - optional external agents (Hermes/OpenClaw/Agent Zero) via their
#         official installers
#       - tests + verify
#
# Usage:
#   ./scripts/setup.sh                # interactive wizard (recommended)
#   ./scripts/setup.sh --no-agents    # wizard, skip external agents
#   ./scripts/setup.sh --skip-tests   # wizard, don't run pytest
#   (non-interactive shell -> runs with defaults, no prompts)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NO_AGENTS=0
SKIP_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --no-agents) NO_AGENTS=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

echo "=============================================="
echo " CouncilKey-Os setup"
echo "=============================================="

# 1. Python environment + package (always needed for the wizard too)
echo ""
echo "[1/2] Installing CouncilKey-Os..."
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install -q -e "$ROOT[dev]"
echo "      ok - 'councilkey' CLI ready"

# 2. Interactive wizard (asks: provider, API key, external agents)
WIZARD_ARGS=""
[ "$NO_AGENTS" -eq 1 ] && WIZARD_ARGS="$WIZARD_ARGS --no-agents"
[ "$SKIP_TESTS" -eq 1 ] && WIZARD_ARGS="$WIZARD_ARGS --skip-tests"

if [ -t 0 ] && [ -t 1 ]; then
  # interactive terminal -> guided wizard with prompts (API keys etc.)
  exec "$ROOT/.venv/bin/councilkey" setup $WIZARD_ARGS
else
  # non-interactive (CI/pipes) -> just install the package, skip prompts
  echo "[2/2] Non-interactive shell - skipping wizard prompts."
  echo "      Run the wizard anytime:  councilkey setup"
  "$ROOT/.venv/bin/councilkey" doctor || true
fi
