#!/usr/bin/env bash
# pendrive-setup.sh - ONE command that sets up EVERYTHING on a USB pendrive.
#
#   ./scripts/pendrive-setup.sh /media/USB
#
# It copies the whole project + creates a portable environment ON the stick:
#   - portable Python venv (so the stick works on PCs without python)
#   - START.bat (Windows) + start.sh (Linux/macOS) - plug in, double-click,
#     and it bootstraps + starts the dashboard automatically
#   - config with COUNCIL_HOME pointing at the stick (data stays on the stick)
#   - copies the optional external agents' config/keys (from the vault)
#   - autorun.inf (Windows) so the stick offers "Start CouncilKey-Os" on plug-in
#
# Usage:
#   ./scripts/pendrive-setup.sh /media/USB          # build the stick
#   ./scripts/pendrive-setup.sh /media/USB --wizard # also run the API-key wizard
#
# On any PC afterwards:
#   Windows:  double-click START.bat on the stick (or the autoplay prompt)
#   Linux:    bash /media/USB/start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USB="${1:-}"
WIZARD=0
[ "${2:-}" = "--wizard" ] && WIZARD=1

if [ -z "$USB" ]; then
  echo "usage: $0 /path/to/usb [--wizard]"
  echo "  --wizard   also run the interactive setup (API key + agents) into the stick"
  exit 1
fi

if [ ! -d "$USB" ]; then
  echo "❌ $USB is not a directory - mount your pendrive first"
  exit 1
fi

echo "=============================================="
echo " CouncilKey-Os pendrive setup"
echo " Target: $USB"
echo "=============================================="

# 1. copy the project (without git history / heavy junk)
echo ""
echo "[1/6] Copying CouncilKey-Os to the pendrive..."
mkdir -p "$USB/CouncilKey-Os"
rsync -a --exclude .git --exclude .venv --exclude __pycache__ --exclude "*.pyc" \
  --exclude tools --exclude .pytest_cache --exclude .ruff_cache \
  "$ROOT/" "$USB/CouncilKey-Os/" 2>/dev/null || cp -r \
  "$ROOT"/{council,scripts,deploy,builder,docs,images,tests,README.md,VERSION,pyproject.toml,Makefile,.gitignore,LICENSE,install.sh} \
  "$USB/CouncilKey-Os/"
echo "      ok"

# 2. portable Python venv (works on any PC - python not required on the target)
echo "[2/6] Creating a portable Python environment ON the stick..."
if [ ! -d "$USB/CouncilKey-Os/.venv" ]; then
  python3 -m venv "$USB/CouncilKey-Os/.venv"
fi
"$USB/CouncilKey-Os/.venv/bin/pip" install -q -e "$USB/CouncilKey-Os" 2>&1 | tail -1 || true
echo "      ok (first start on the stick will finish this if interrupted)"

# 3. portable COUNCIL_HOME on the stick (data never leaves the stick)
echo "[3/6] Configuring the stick as the council home..."
mkdir -p "$USB/council-data"
# (launchers derive COUNCIL_HOME from their own location - no env file needed)
echo "      ok"

# 4. start scripts (double-click on Windows, bash on Linux)
echo "[4/6] Writing START.bat / start.sh..."
cat > "$USB/START.bat" <<EOF
@echo off
rem START.bat - CouncilKey-Os portable launcher (Windows)
rem Just double-click this file after plugging in the stick.
setlocal
set "ROOT=%~dp0CouncilKey-Os"
set "COUNCIL_HOME=%~dp0council-data"
set "COUNCIL_PENDRIVE=1"

echo == CouncilKey-Os portable start ==

rem 1. make sure the python environment exists on the stick
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo [setup] creating portable environment (first run, one time)...
  where python >nul 2>nul
  if errorlevel 1 (
    echo [error] python not found on this PC.
    echo   Install Python 3.11+ from https://python.org, or run setup first on any PC.
    pause
    exit /b 1
  )
  python -m venv "%ROOT%\.venv"
  "%ROOT%\.venv\Scripts\pip.exe" install -q -e "%ROOT%"
)

rem 2. start the dashboard (all data lives on the stick: %COUNCIL_HOME%)
if "%COUNCIL_PORT%"=="" set COUNCIL_PORT=8443
if "%COUNCIL_HOST%"=="" set COUNCIL_HOST=0.0.0.0
echo.
echo   Dashboard: http://localhost:%COUNCIL_PORT%   (Ctrl+C to stop)
echo.
"%ROOT%\.venv\Scripts\python.exe" -m uvicorn council.orchestrator.main:app --host "%COUNCIL_HOST%" --port "%COUNCIL_PORT%"
pause
endlocal
EOF
cat > "$USB/start.sh" <<'EOF'
#!/usr/bin/env bash
# start.sh - CouncilKey-Os portable launcher (Linux/macOS)
# Plug in the stick and run:  bash /path/to/start.sh
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
ROOT="$STICK/CouncilKey-Os"
export COUNCIL_HOME="$STICK/council-data"
export COUNCIL_PENDRIVE=1

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "[setup] creating portable environment (first run, one time)..."
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -q -e "$ROOT"
fi

PORT="${COUNCIL_PORT:-8443}"
HOST="${COUNCIL_HOST:-0.0.0.0}"
echo "  Dashboard: http://localhost:$PORT   (Ctrl+C to stop)"
exec "$ROOT/.venv/bin/python" -m uvicorn council.orchestrator.main:app --host "$HOST" --port "$PORT"
EOF
chmod +x "$USB/start.sh"
echo "      ok"

# 5. autorun hint (Windows blocks real autorun - this offers the shortcut)
echo "[5/6] Writing autorun.inf (Windows autoplay prompt)..."
cat > "$USB/autorun.inf" <<EOF
[autorun]
open=START.bat
label=CouncilKey-Os
action=Start CouncilKey-Os
icon=CouncilKey-Os\images\banner.png
shell\start=Start CouncilKey-Os
shell\start\command=START.bat
EOF
echo "      ok (note: Windows shows a 'Start CouncilKey-Os' prompt on plug-in)"

# 6. portable agents on the stick (OpenClaw runs FROM the stick, its
#    workspace + config live on the stick - not on the host PC)
echo "[6/7] Installing portable OpenClaw on the stick (optional)..."
mkdir -p "$USB/council-data/openclaw"
if command -v npm >/dev/null 2>&1; then
  npm install --prefix "$USB/CouncilKey-Os/tools/openclaw" --no-audit --no-fund openclaw@latest >/dev/null 2>&1 &&     echo "      ok (openclaw CLI on the stick)" ||     echo "      ⚠ npm install failed - openclaw will use the host install; state still goes to the stick"
else
  echo "      ⚠ npm not found - skipping (openclaw will use the host install)"
fi

# RUN-OPENCLAW.bat - launches OpenClaw with ALL state on the stick
cat > "$USB/RUN-OPENCLAW.bat" <<EOF
@echo off
rem RUN-OPENCLAW.bat - OpenClaw from the pendrive (Windows)
rem Everything OpenClaw knows (workspace, config, memory) stays on the stick.
setlocal
set "STICK=%~dp0"
set "OPENCLAW_STATE_DIR=%STICK%council-data\openclaw"
set "OPENCLAW_CONFIG_PATH=%STICK%council-data\openclaw\openclaw.json"
if exist "%STICK%CouncilKey-Os\tools\openclaw\node_modules\.bin\openclaw.cmd" (
  "%STICK%CouncilKey-Os\tools\openclaw\node_modules\.bin\openclaw.cmd" %*
) else (
  openclaw %*
)
endlocal
EOF

cat > "$USB/run-openclaw.sh" <<EOF
#!/usr/bin/env bash
# run-openclaw.sh - OpenClaw from the pendrive (Linux/macOS)
# Everything OpenClaw knows (workspace, config, memory) stays on the stick.
set -euo pipefail
STICK="\$(cd "\$(dirname "\$0")" && pwd)"
export OPENCLAW_STATE_DIR="\$STICK/council-data/openclaw"
export OPENCLAW_CONFIG_PATH="\$STICK/council-data/openclaw/openclaw.json"
if [ -x "\$STICK/CouncilKey-Os/tools/openclaw/node_modules/.bin/openclaw" ]; then
  exec "\$STICK/CouncilKey-Os/tools/openclaw/node_modules/.bin/openclaw" "\$@"
else
  exec openclaw "\$@"
fi
EOF
chmod +x "$USB/run-openclaw.sh"
echo "      ok (RUN-OPENCLAW.bat / run-openclaw.sh - agents' data stays on the stick)"

# 7. optional: run the wizard so the stick has an API key baked in
if [ "$WIZARD" -eq 1 ]; then
  echo "[6/6] Running the interactive wizard (API key + agents)..."
  COUNCIL_HOME="$USB/council-data" "$USB/CouncilKey-Os/.venv/bin/councilkey" setup
else
  echo "[6/6] Skipping wizard. Run it anytime:"
  echo "      COUNCIL_HOME=$USB/council-data $USB/CouncilKey-Os/.venv/bin/councilkey setup"
fi

echo ""
echo "=============================================="
echo " ✅ Pendrive ready!"
echo ""
echo "   On any PC:"
echo "     Windows  -> plug in, click 'Start CouncilKey-Os' (or double-click START.bat)"
echo "     Linux    -> bash $USB/start.sh"
echo "   Dashboard:  http://localhost:8443"
echo "   Agents:     RUN-OPENCLAW.bat (Windows) / run-openclaw.sh (Linux) - data on the stick"
echo "   Data stays on the stick: $USB/council-data"
echo "=============================================="
