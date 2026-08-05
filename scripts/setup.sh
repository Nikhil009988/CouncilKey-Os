#!/usr/bin/env bash
# setup.sh - One-command setup for CouncilKey-Os.
#
# Does everything:
#   1. creates the Python environment and installs CouncilKey-Os
#   2. DOWNLOADS the 3 agents automatically (Hermes, OpenClaw, Agent Zero)
#      from their official repos into tools/linux/
#   3. installs each agent's dependencies
#   4. runs the test suite (optional)
#   5. shows the final agent status
#
# Usage:
#   ./scripts/setup.sh                # full setup (downloads the 3 agents)
#   ./scripts/setup.sh --skip-agents  # only install CouncilKey-Os itself
#   ./scripts/setup.sh --skip-tests   # don't run pytest at the end
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKIP_AGENTS=0
SKIP_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --skip-agents) SKIP_AGENTS=1 ;;
    --skip-tests)  SKIP_TESTS=1 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

echo "=============================================="
echo " CouncilKey-Os setup"
echo "=============================================="

# 1. Python environment + package
echo ""
echo "[1/4] Installing CouncilKey-Os (Python environment)..."
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install -q -e "$ROOT[dev]"
echo "      ok - 'councilkey' CLI ready"

# 2. Download the 3 agents
if [ "$SKIP_AGENTS" -eq 1 ]; then
  echo "[2/4] Skipping agent download (--skip-agents)"
else
  echo "[2/4] Downloading the 3 agents (Hermes, OpenClaw, Agent Zero)..."
  echo "      This downloads their official repos - can take a few minutes"
  echo "      on the first run (needs an internet connection + git)."
  "$ROOT/.venv/bin/councilkey" agents install || {
    echo ""
    echo "      ⚠ agent download incomplete."
    echo "        - no internet? retry later with:  councilkey agents install"
    echo "        - or continue now; the council runs in mock mode until"
    echo "          the agents are installed."
  }
fi

# 3. Tests
if [ "$SKIP_TESTS" -eq 1 ]; then
  echo "[3/4] Skipping tests (--skip-tests)"
else
  echo "[3/4] Running the test suite..."
  (cd "$ROOT" && "$ROOT/.venv/bin/python" -m pytest tests -q) || true
fi

# 4. Final status
echo ""
echo "[4/4] Agent status:"
"$ROOT/.venv/bin/councilkey" agents status || true

echo ""
echo "=============================================="
echo " ✅ Setup complete"
echo ""
echo "   Start the dashboard + API:   ./scripts/start.sh"
echo "                                (or: .venv/bin/councilkey serve)"
echo "   Open:                        http://localhost:8443"
echo "   Agent status anytime:        .venv/bin/councilkey agents status"
echo "   Start agents:                .venv/bin/councilkey agents start"
echo "=============================================="
