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
NO_AGENTS=0
for arg in "${@:2}"; do
  case "$arg" in
    --wizard) WIZARD=1 ;;
    --no-agents) NO_AGENTS=1 ;;
    *) ;;
  esac
done

if [ -z "$USB" ]; then
  echo "usage: $0 /path/to/usb [--wizard] [--no-agents]"
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
echo   Running from: %~dp0  (all data on the stick)

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

# 6. ALL agents on the stick - nothing runs from the host PC
echo "[6/8] Installing the agents ONTO the stick (everything stays on the stick)..."
if [ "$NO_AGENTS" -eq 1 ]; then
  echo "      skipped agent installs (--no-agents) - launchers are still written"
else
  STICK_VENV="$USB/CouncilKey-Os/.venv"
  mkdir -p "$USB/council-data/agents"

  # --- Python agents into the stick venv (hermes, crewai, aider) ---
  PIP="$STICK_VENV/bin/pip"; [ -x "$STICK_VENV/Scripts/pip.exe" ] && PIP="$STICK_VENV/Scripts/pip.exe"
  if [ -x "$PIP" ]; then
    echo "      installing hermes-agent, crewai, aider-chat into the stick venv (one command, can take a few minutes)..."
    "$PIP" install -q hermes-agent crewai aider-chat 2>/dev/null && \
      echo "      ok (hermes + crewai + aider on the stick)" || \
      echo "      ⚠ pip install of agents failed - re-run on a machine with internet"
  else
    echo "      ⚠ stick venv not found - agents skipped"
  fi

  # --- OpenClaw via npm into the stick ---
  echo "      installing openclaw onto the stick (npm)..."
  mkdir -p "$USB/council-data/openclaw"
  if command -v npm >/dev/null 2>&1; then
    npm install --prefix "$USB/CouncilKey-Os/tools/openclaw" --no-audit --no-fund openclaw@latest >/dev/null 2>&1 && \
      echo "      ok (openclaw CLI on the stick)" || \
      echo "      ⚠ npm install failed - openclaw will use the host install; state still goes to the stick"
  else
    echo "      ⚠ npm not found - openclaw will use the host install"
  fi

fi
# --- launchers: every agent runs from the stick with state on the stick ---
cat > "$USB/RUN-OPENCLAW.bat" <<'EOF'
@echo off
rem RUN-OPENCLAW.bat - OpenClaw from the pendrive (Windows)
rem Every path OpenClaw uses (state, config, workspace, home) is on the stick.
echo == OpenClaw from the pendrive ==
echo   Running from: %~dp0
setlocal
set "STICK=%~dp0"
set "OPENCLAW_STATE_DIR=%STICK%council-data\openclaw"
set "OPENCLAW_CONFIG_PATH=%STICK%council-data\openclaw\openclaw.json"
set "OPENCLAW_WORKSPACE_DIR=%STICK%council-data\openclaw\workspace"
set "OPENCLAW_HOME=%STICK%council-data\openclaw\home"
if not exist "%STICK%council-data\openclaw\workspace" mkdir "%STICK%council-data\openclaw\workspace"
if exist "%STICK%CouncilKey-Os\tools\openclaw\node_modules\.bin\openclaw.cmd" (
  "%STICK%CouncilKey-Os\tools\openclaw\node_modules\.bin\openclaw.cmd" %*
) else (
  openclaw %*
)
endlocal
EOF

cat > "$USB/run-openclaw.sh" <<'EOF'
#!/usr/bin/env bash
# run-openclaw.sh - OpenClaw from the pendrive (Linux/macOS)
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
export OPENCLAW_STATE_DIR="$STICK/council-data/openclaw"
export OPENCLAW_CONFIG_PATH="$STICK/council-data/openclaw/openclaw.json"
export OPENCLAW_WORKSPACE_DIR="$STICK/council-data/openclaw/workspace"
export OPENCLAW_HOME="$STICK/council-data/openclaw/home"
mkdir -p "$OPENCLAW_WORKSPACE_DIR" "$OPENCLAW_HOME"
echo "== OpenClaw from the pendrive =="
echo "  Running from: $STICK"
if [ -x "$STICK/CouncilKey-Os/tools/openclaw/node_modules/.bin/openclaw" ]; then
exec "$STICK/CouncilKey-Os/tools/openclaw/node_modules/.bin/openclaw" "$@"
else
exec openclaw "$@"
fi
EOF

cat > "$USB/RUN-HERMES.bat" <<'EOF'
@echo off
rem RUN-HERMES.bat - Hermes from the pendrive (Windows)
setlocal
set "STICK=%~dp0"
set "HERMES_HOME=%STICK%council-datagents\hermes"
if exist "%STICK%CouncilKey-Os\.venv\Scripts\hermes.exe" (
"%STICK%CouncilKey-Os\.venv\Scripts\hermes.exe" %*
) else (
echo [error] hermes not on the stick - rebuild the stick with internet
pause
)
endlocal
EOF

cat > "$USB/run-hermes.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
export HERMES_HOME="$STICK/council-data/agents/hermes"
if [ -x "$STICK/CouncilKey-Os/.venv/bin/hermes" ]; then
exec "$STICK/CouncilKey-Os/.venv/bin/hermes" "$@"
else
echo "[error] hermes not on the stick - rebuild the stick with internet" >&2
exit 1
fi
EOF

cat > "$USB/RUN-CREWAI.bat" <<'EOF'
@echo off
rem RUN-CREWAI.bat - CrewAI from the pendrive (Windows)
setlocal
set "STICK=%~dp0"
if exist "%STICK%CouncilKey-Os\.venv\Scripts\crewai.exe" (
"%STICK%CouncilKey-Os\.venv\Scripts\crewai.exe" %*
) else (
echo [error] crewai not on the stick - rebuild the stick with internet
pause
)
endlocal
EOF

cat > "$USB/run-crewai.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$STICK/CouncilKey-Os/.venv/bin/crewai" ]; then
exec "$STICK/CouncilKey-Os/.venv/bin/crewai" "$@"
else
echo "[error] crewai not on the stick - rebuild the stick with internet" >&2
exit 1
fi
EOF

cat > "$USB/RUN-AIDER.bat" <<'EOF'
@echo off
rem RUN-AIDER.bat - Aider from the pendrive (Windows)
setlocal
set "STICK=%~dp0"
if exist "%STICK%CouncilKey-Os\.venv\Scriptsider.exe" (
"%STICK%CouncilKey-Os\.venv\Scriptsider.exe" %*
) else (
echo [error] aider not on the stick - rebuild the stick with internet
pause
)
endlocal
EOF

cat > "$USB/run-aider.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$STICK/CouncilKey-Os/.venv/bin/aider" ]; then
exec "$STICK/CouncilKey-Os/.venv/bin/aider" "$@"
else
echo "[error] aider not on the stick - rebuild the stick with internet" >&2
exit 1
fi
EOF

cat > "$USB/RUN-CODEX.bat" <<'EOF'
@echo off
rem RUN-CODEX.bat - Codex CLI from the pendrive (Windows) - NO Docker needed
rem Codex runs locally: terminal, file editing and web tools on this PC.
rem State and config stay on the stick (council-data\codex).
setlocal
set "STICK=%~dp0"
set "CODEX_HOME=%STICK%council-data\codex"
set "CODECONFIG=%STICK%council-data\codex\config.toml"
if not exist "%CODEX_HOME%" mkdir "%CODEX_HOME%"

rem 1. point Codex at the provider key stored in the encrypted vault
call "%~dp0CouncilKey-Os\councilkey.bat" agents configure codex
if errorlevel 1 (
  echo [error] no API key configured yet.
  echo   Run once:  councilkey.bat setup   (choose OpenAI or OpenRouter)
  pause
  exit /b 1
)
for /f "delims=" %%K in ('"%~dp0CouncilKey-Os\councilkey.bat" key show OPENROUTER_API_KEY 2^>nul') do set "OPENROUTER_API_KEY=%%K"
for /f "delims=" %%K in ('"%~dp0CouncilKey-Os\councilkey.bat" key show OPENAI_API_KEY 2^>nul') do set "OPENAI_API_KEY=%%K"

rem 2. run codex (from the stick if installed there, else the PC install)
if exist "%STICK%CouncilKey-Os\tools\codex\node_modules\.bin\codex.cmd" (
  "%STICK%CouncilKey-Os\tools\codex\node_modules\.bin\codex.cmd" %*
) else (
  codex %*
)
endlocal
EOF

cat > "$USB/run-codex.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
export CODEX_HOME="$STICK/council-data/codex"
export CODECONFIG="$STICK/council-data/codex/config.toml"
mkdir -p "$CODEX_HOME"
"$STICK/CouncilKey-Os/councilkey" agents configure codex
export OPENROUTER_API_KEY="$("$STICK/CouncilKey-Os/councilkey" key show OPENROUTER_API_KEY 2>/dev/null || true)"
export OPENAI_API_KEY="$("$STICK/CouncilKey-Os/councilkey" key show OPENAI_API_KEY 2>/dev/null || true)"
exec codex "$@"
EOF

chmod +x "$USB"/run-*.sh
echo "      ok (launchers: RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-CODEX)"


# 7. session mode + agent menu + launch-all + stick README
echo "[7/8] Writing session-mode, agent menu and launch-all launchers..."

# --- session mode: code cloned to the PC for speed, MEMORY stays on the
#     stick, and the session is wiped when it ends (no traces on the PC) ---
cat > "$USB/start-session.sh" <<'EOF'
#!/usr/bin/env bash
# start-session.sh - SESSION MODE (Linux/macOS)
# Clones the code to this PC (fast), keeps ALL data/memory on the stick,
# and wipes the PC copy when the session ends.
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
ROOT="$STICK/CouncilKey-Os"
export COUNCIL_HOME="$STICK/council-data"
export COUNCIL_PENDRIVE=1
SESSION="${TMPDIR:-/tmp}/councilkey-session"
rm -rf "$SESSION"
mkdir -p "$SESSION"
cp -r "$ROOT"/council "$ROOT"/VERSION "$ROOT"/pyproject.toml "$SESSION"/
echo "== CouncilKey-Os SESSION mode =="
echo "  code:   $SESSION (temporary, wiped on end)"
echo "  memory: $COUNCIL_HOME (stays on the stick)"
echo "  dashboard: http://localhost:${COUNCIL_PORT:-8443}  (Ctrl+C to stop)"
cd "$SESSION"
echo $$ > "$SESSION/server.pid"
exec "$ROOT/.venv/bin/python" -m uvicorn council.orchestrator.main:app --host 0.0.0.0 --port "${COUNCIL_PORT:-8443}"
EOF

cat > "$USB/end-session.sh" <<'EOF'
#!/usr/bin/env bash
# end-session.sh - stop the session and WIPE it from this PC
set -u
SESSION="${TMPDIR:-/tmp}/councilkey-session"
if [ -f "$SESSION/server.pid" ]; then
  kill "$(cat "$SESSION/server.pid")" 2>/dev/null || true
  sleep 1
fi
rm -rf "$SESSION"
echo "== session ended =="
echo "  PC copy deleted - nothing left on this PC."
echo "  Memory is safe on the stick: council-data/"
EOF

cat > "$USB/START-SESSION.bat" <<'EOF'
@echo off
rem START-SESSION.bat - SESSION MODE (Windows)
rem Clones the code to this PC (fast), keeps ALL data/memory on the stick,
rem and wipes the PC copy when the session ends (END-SESSION.bat).
setlocal
set "STICK=%~dp0"
set "ROOT=%STICK%CouncilKey-Os"
set "COUNCIL_HOME=%STICK%council-data"
set "COUNCIL_PENDRIVE=1"
set "SESSION=%TEMP%\councilkey-session"

echo == CouncilKey-Os SESSION mode ==
echo   code:   %SESSION% (temporary, wiped on end)
echo   memory: %COUNCIL_HOME% (stays on the stick)
echo.

if exist "%SESSION%" rmdir /s /q "%SESSION%"
mkdir "%SESSION%"
xcopy /e /i /q /y "%ROOT%\council" "%SESSION%\council" >nul
copy /y "%ROOT%\VERSION" "%SESSION%" >nul
copy /y "%ROOT%\pyproject.toml" "%SESSION%" >nul

echo   dashboard: http://localhost:8443  (close this window to stop)
echo.
cd /d "%SESSION%"
"%ROOT%\.venv\Scripts\python.exe" -m uvicorn council.orchestrator.main:app --host 0.0.0.0 --port 8443
endlocal
EOF

cat > "$USB/END-SESSION.bat" <<'EOF'
@echo off
rem END-SESSION.bat - stop the session and WIPE it from this PC
set "SESSION=%TEMP%\councilkey-session"
if exist "%SESSION%" rmdir /s /q "%SESSION%"
echo == session ended ==
echo   PC copy deleted - nothing left on this PC.
echo   Memory is safe on the stick: council-datapause
EOF

# --- agent menu: use ANY one agent, or ALL at once ---
cat > "$USB/AGENTS.bat" <<'EOF'
@echo off
rem AGENTS.bat - choose what to run (any agent, or everything at once)
:menu
cls
echo ==============================================
echo  CouncilKey-Os - what do you want to run?
echo ==============================================
echo   A) ALL agents + dashboard  (everything at once)
echo   1) Dashboard  (council chat: 3 agents + vote)
echo   2) OpenClaw
echo   3) Hermes
echo   4) CrewAI
echo   5) Aider
echo   6) Codex  (local agent - no Docker)
echo   0) Quit
echo ==============================================
set /p choice="Choose (A/1-6/0): "
if /i "%choice%"=="A" goto all
if "%choice%"=="1" goto dash
if "%choice%"=="2" goto oc
if "%choice%"=="3" goto hermes
if "%choice%"=="4" goto crewai
if "%choice%"=="5" goto aider
if "%choice%"=="6" goto codex
if "%choice%"=="0" exit /b 0
goto menu
:all
start "Council Dashboard" cmd /c "%~dp0START.bat"
start "OpenClaw" cmd /c "%~dp0RUN-OPENCLAW.bat"
start "Hermes" cmd /c "%~dp0RUN-HERMES.bat"
start "CrewAI" cmd /c "%~dp0RUN-CREWAI.bat"
start "Aider" cmd /c "%~dp0RUN-AIDER.bat"
start "Codex" cmd /c "%~dp0RUN-CODEX.bat"
goto done
:dash
call "%~dp0START.bat"
goto done
:oc
call "%~dp0RUN-OPENCLAW.bat"
goto done
:hermes
call "%~dp0RUN-HERMES.bat"
goto done
:crewai
call "%~dp0RUN-CREWAI.bat"
goto done
:aider
call "%~dp0RUN-AIDER.bat"
goto done
:codex
call "%~dp0RUN-CODEX.bat"
goto done
:done
echo.
echo  (run AGENTS.bat again to choose something else)
pause
goto menu
EOF

cat > "$USB/agents-menu.sh" <<'EOF'
#!/usr/bin/env bash
# agents-menu.sh - choose what to run (any agent, or everything at once)
STICK="$(cd "$(dirname "$0")" && pwd)"
echo "=============================================="
echo " CouncilKey-Os - what do you want to run?"
echo "=============================================="
echo "  A) ALL agents + dashboard  (everything at once)"
echo "  1) Dashboard  (council chat: 3 agents + vote)"
echo "  2) OpenClaw"
echo "  3) Hermes"
echo "  4) CrewAI"
echo "  5) Aider"
echo "  6) Codex  (local agent - no Docker)"
echo "  0) Quit"
echo "=============================================="
read -rp "Choose (A/1-6/0): " choice
case "$choice" in
  A|a)
    bash "$STICK/start.sh" &
    bash "$STICK/run-openclaw.sh" &
    bash "$STICK/run-hermes.sh" &
    bash "$STICK/run-crewai.sh" &
    bash "$STICK/run-aider.sh" &
    bash "$STICK/run-codex.sh" &
    ;;
  1) bash "$STICK/start.sh" ;;
  2) bash "$STICK/run-openclaw.sh" ;;
  3) bash "$STICK/run-hermes.sh" ;;
  4) bash "$STICK/run-crewai.sh" ;;
  5) bash "$STICK/run-aider.sh" ;;
  6) bash "$STICK/run-codex.sh" ;;
  0) exit 0 ;;
  *) echo "try again"; bash "$0" ;;
esac
EOF
chmod +x "$USB/agents-menu.sh" "$USB/start-session.sh" "$USB/end-session.sh"

# --- launch-all: everything at once, directly ---
cat > "$USB/launch-all.sh" <<'EOF'
#!/usr/bin/env bash
# launch-all.sh - start EVERYTHING at once (dashboard + all agents)
STICK="$(cd "$(dirname "$0")" && pwd)"
bash "$STICK/start.sh" &
sleep 2
for launcher in run-openclaw.sh run-hermes.sh run-crewai.sh run-aider.sh run-codex.sh; do
  [ -x "$STICK/$launcher" ] && bash "$STICK/$launcher" &
done
echo "all agents launched - dashboard at http://localhost:8443"
wait
EOF
chmod +x "$USB/launch-all.sh"

# --- README on the stick ---
cat > "$USB/PENDRIVE-README.txt" <<EOF
==============================================
 CouncilKey-Os - PENDRAVE GUIDE (read me)
==============================================

WHAT YOU HAVE
  This stick contains the whole CouncilKey-Os: the app, a portable
  Python environment, and all 5 agents (Hermes, OpenClaw, Codex,
  CrewAI, Aider). Codex is the builder/review agent - terminal, file
  editing and web tools, runs locally, NO Docker.
  ALL data - journal, memory, API keys, agent
  workspaces - lives on this stick in the "council-data" folder.

START ANY AGENT OR EVERYTHING AT ONCE
  Windows:  double-click AGENTS.bat  -> menu: A = ALL, 1-6 = one agent
  Linux:    bash agents-menu.sh
  Or directly:
    START.bat          dashboard (council chat: 3 agents + vote)
    RUN-OPENCLAW.bat   OpenClaw      RUN-HERMES.bat   Hermes
    RUN-CREWAI.bat     CrewAI        RUN-AIDER.bat    Aider
    RUN-CODEX.bat      Codex (local)     LAUNCH-ALL.bat   everything

SESSION MODE (clone to PC, memory on stick, no traces)
  The stick runs everything by itself. Want it FASTER on this PC?
    start-session.bat  -> copies the code to this PC temporarily,
                           MEMORY stays on the stick
    end-session.bat    -> stops it and DELETES the PC copy
  Unplug the stick any time: nothing of yours is on this PC.

FIRST TIME ON A NEW PC
  1. The first start creates the portable environment (a few minutes).
  2. The agents need an API key to answer. Run:
       councilkey.bat setup
     (choose OpenAI / Anthropic / Gemini / OpenRouter, paste the key -
      it is stored encrypted on the stick)
  3. councilkey.bat agents verify   -> confirms everything works

EVERYTHING STAYS ON THE STICK
  council-data/  = journal, memory, API keys, agent workspaces
  Unplug -> this PC is exactly as it was before.
==============================================
EOF
echo "      ok (session mode, agent menu, launch-all, PENDRIVE-README.txt)"

# 8. optional: run the wizard so the stick has an API key baked in
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
echo "   Agents:     RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-CODEX (.bat)"
echo "               or run-*.sh on Linux - ALL on the stick, data stays on the stick"
echo "   Data stays on the stick: $USB/council-data"
echo "=============================================="
