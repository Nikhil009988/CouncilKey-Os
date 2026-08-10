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
#   ./scripts/pendrive-setup.sh /media/USB          # build the stick (asks which agents)
#   ./scripts/pendrive-setup.sh /media/USB --wizard # also run the API-key wizard
#   ./scripts/pendrive-setup.sh /media/USB --check  # check everything first, install nothing
#   ./scripts/pendrive-setup.sh /media/USB --agents 1,3,5   # install only those
#
# On any PC afterwards:
#   Windows:  double-click START.bat on the stick (or the autoplay prompt)
#   Linux:    bash /media/USB/start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USB="${1:-}"
WIZARD=0
NO_AGENTS=0
CHECK=0
AGENTS=""
_args=("${@:2}")
_i=0
while [ $_i -lt ${#_args[@]} ]; do
  case "${_args[$_i]}" in
    --wizard) WIZARD=1 ;;
    --no-agents) NO_AGENTS=1 ;;
    --check) CHECK=1 ;;
    --agents) AGENTS="${_args[$((_i + 1))]:-}"; _i=$((_i + 1)) ;;
  esac
  _i=$((_i + 1))
done

if [ -z "$USB" ]; then
  echo "usage: $0 /path/to/usb [--wizard] [--no-agents] [--check] [--agents 1,3,5]"
  echo "  --wizard     also run the interactive setup (API key + agents) into the stick"
  echo "  --check      check prerequisites + internet first, install NOTHING"
  echo "  --agents N   only install the listed agents (numbers/names, e.g. 1,3,5 or hermes,opencode)"
  echo "  (default: asks you which agents to install)"
  exit 1
fi

if [ ! -d "$USB" ]; then
  echo "❌ $USB is not a directory - mount your pendrive first"
  exit 1
fi

echo "=============================================="
echo " CouncilKey-Os pendrive setup v1.23.0"
echo "  - ASKS which agents to install (nothing automatic)"
echo "  - use --check first to inspect everything"
echo " Target: $USB"
echo "=============================================="


# ---- CHECK MODE: see everything first, install NOTHING ----
if [ "$CHECK" -eq 1 ]; then
  STICK_VENV="$USB/CouncilKey-Os/.venv"
  PIP="$STICK_VENV/bin/pip"; [ -x "$STICK_VENV/Scripts/pip.exe" ] && PIP="$STICK_VENV/Scripts/pip.exe"
  net_ok() { # $1 = hostname
    if command -v timeout >/dev/null 2>&1; then
      timeout 4 bash -c "echo > /dev/tcp/$1/443" 2>/dev/null && echo "reachable" || echo "NOT reachable"
    else
      echo "? (no timeout tool)"
    fi
  }
  echo ""
  echo "  == Pre-install check (nothing installed) =="
  echo "  stick venv      : $([ -x "$PIP" ] && echo ready || echo 'MISSING - run without --check first to build')"
  echo "  python (PC)     : $(command -v python3 >/dev/null 2>&1 && echo ok || echo 'missing (install Python 3.11+)')"
  echo "  npm (PC)        : $(command -v npm >/dev/null 2>&1 && echo ok || echo 'missing (OpenClaw/OpenCode need it)')"
  echo "  internet PyPI   : $(net_ok pypi.org)"
  echo "  internet npmjs  : $(net_ok registry.npmjs.org)"
  if [ -x "$PIP" ]; then
    have=$("$PIP" list 2>/dev/null | grep -E 'hermes-agent|crewai|aider-chat' | awk '{print $1}' | tr '\n' ' ' || true)
    for n in openclaw opencode; do
      [ -d "$USB/CouncilKey-Os/tools/$n/node_modules/.bin" ] && have="$have $n"
    done
    echo "  already on stick: ${have:-none yet}"
  fi
  free_mb=$(df -Pm "$USB" 2>/dev/null | awk 'NR==2 {print $4}')
  if [ -n "$free_mb" ]; then
    free_gb=$(awk "BEGIN {printf \"%.1f\", $free_mb/1024}")
    if [ "$free_mb" -lt 4096 ]; then
      echo "  stick free space : ${free_gb} GB  ⚠ LOW - agents need ~3-4 GB free"
    else
      echo "  stick free space : ${free_gb} GB (ok)"
    fi
  fi
  echo "  TIP: if an install hangs >20 min, Ctrl+C and re-run - it resumes"
  echo "       from where it stopped (copy/venv are skipped, downloads resume)."
  echo ""
  echo "  Choose what to install, then re-run:"
  echo "    ./scripts/pendrive-setup.sh $USB --agents 1,3,5   (or run without --agents to pick interactively)"
  exit 0
fi


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
echo "[2/6] Building the portable Python environment (on the PC, then copy to the stick)..."
WORK_ROOT="${TMPDIR:-/tmp}/councilkey-stick-build"
WORK_VENV="$WORK_ROOT/venv"
mkdir -p "$WORK_ROOT"
if [ -x "$WORK_VENV/bin/python" ]; then
  "$WORK_VENV/bin/python" -c "import council" 2>/dev/null || rm -rf "$WORK_VENV"
fi
if [ ! -x "$WORK_VENV/bin/python" ]; then
  echo "      creating the PC work venv (one time)..."
  python3 -m venv "$WORK_VENV" || { echo "❌ could not create the venv"; exit 1; }
fi
"$WORK_VENV/bin/pip" install --retries 20 --timeout 90 -q -e "$ROOT" 2>&1 | tail -1 || true
# clean stale pip temp dirs on the stick, then copy (incremental)
STICK_VENV="$USB/CouncilKey-Os/.venv"
if [ -d "$STICK_VENV/lib/python3*/site-packages" ]; then
  find "$STICK_VENV" -maxdepth 4 -type d -name '~*' -exec rm -rf {} + 2>/dev/null || true
fi
mkdir -p "$STICK_VENV"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$WORK_VENV/" "$STICK_VENV/" 2>/dev/null || true
else
  cp -a "$WORK_VENV/." "$STICK_VENV/" 2>/dev/null || true
fi
echo "      ok (portable venv on the stick)"

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
set "LOG=%COUNCIL_HOME%\startup.log"
if not exist "%COUNCIL_HOME%" mkdir "%COUNCIL_HOME%"

echo == CouncilKey-Os portable start ==
echo   Running from: %~dp0  (all data on the stick)
echo.

rem 1. portable python + app must be complete on the stick
if not exist "%ROOT%\.venv\Scripts\python.exe" goto repair
"%ROOT%\.venv\Scripts\python.exe" -c "import council, uvicorn" >nul 2>&1
if not errorlevel 1 goto portpick
:repair
echo [setup] finishing the portable environment (first run, one time - can take a few minutes)...
where python >nul 2>nul
if errorlevel 1 goto nopython
python -m venv "%ROOT%\.venv"
if errorlevel 1 goto die
rem clean stale pip temp dirs (interrupted installs) before reinstalling
for /d %%D in ("%ROOT%\.venv\Lib\site-packages\~*") do rmdir /s /q "%%D" 2>nul
"%ROOT%\.venv\Scripts\pip.exe" install -q --retries 20 --timeout 90 -e "%ROOT%"
if errorlevel 1 goto die
"%ROOT%\.venv\Scripts\python.exe" -c "import council, uvicorn" >nul 2>&1
if errorlevel 1 goto broken
:portpick
rem 2. pick a free port (8443-8463) - never fail just because 8443 is busy
set "PORT=8443"
:portloop
netstat -ano 2>nul | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if errorlevel 1 goto portok
set /a PORT+=1
if %PORT% gtr 8463 goto noports
goto portloop
:portok
echo   Dashboard: http://localhost:%PORT%   (Ctrl+C to stop)
echo.
rem 3. start the dashboard - all output is also written to the stick log
>"%LOG%" 2>&1 "%ROOT%\.venv\Scripts\python.exe" -m uvicorn council.orchestrator.main:app --host 0.0.0.0 --port %PORT%
if errorlevel 1 (
  echo [error] the dashboard stopped. Full log:
  echo   %LOG%
  echo   Paste the last lines to the CouncilKey-Os team for a fix.
)
goto die
:nopython
echo [error] Python is not installed on this PC.
echo   Install Python 3.11+ from https://python.org, then re-run START.bat
goto die
:broken
echo [error] the app on the stick is incomplete (interrupted build).
echo   Rebuild the stick on a PC with internet:
echo     scripts\pendrive-setup.ps1 -Path %~d0 -Agents 1,2,3
goto die
:noports
echo [error] no free port between 8443 and 8463 on this PC.
:die
echo.
echo   (window stays open - press any key to close)
pause >nul
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

# 6. agents ON the stick - YOU CHOOSE what to install (nothing automatic)
echo "[6/8] Agents ONTO the stick (you choose - nothing is installed without asking)..."
mkdir -p "$USB/council-data/agents"
STICK_VENV="$USB/CouncilKey-Os/.venv"
PIP="$STICK_VENV/bin/pip"; [ -x "$STICK_VENV/Scripts/pip.exe" ] && PIP="$STICK_VENV/Scripts/pip.exe"

net_ok() { # $1 = hostname
  if command -v timeout >/dev/null 2>&1; then
    timeout 4 bash -c "echo > /dev/tcp/$1/443" 2>/dev/null && echo "reachable" || echo "NOT reachable"
  else
    echo "? (no timeout tool)"
  fi
}

# ---- choose agents ----
if [ "$NO_AGENTS" -eq 1 ]; then
  echo "      skipped agent installs (--no-agents) - launchers are still written"
else
  SELECTED="$AGENTS"
  if [ -z "$SELECTED" ]; then
    echo ""
    echo "  Which agents do you want ON the stick? (nothing is installed without your choice)"
    echo "    1) Hermes    (pip)     2) OpenClaw  (npm)     3) OpenCode (npm)"
    echo "    4) CrewAI    (pip)     5) Aider     (pip)"
    echo "    A) All 5    0) None"
    read -rp "    Pick (e.g. 1,3,5 or A or 0): " SELECTED
  fi
  SELECTED="$(echo "$SELECTED" | tr 'A-Z' 'a-z' | tr ',' ' ')"
  if [ "$SELECTED" = "a" ] || [ "$SELECTED" = "all" ]; then
    SELECTED="1 2 3 4 5"
  fi
  if [ -z "$SELECTED" ] || [ "$SELECTED" = "0" ] || [ "$SELECTED" = "none" ]; then
    echo "      no agents selected - launchers are still written (install later with --agents)"
  else
    names=""
    for s in $SELECTED; do
      case "$s" in
        1|hermes)   names="$names hermes" ;;
        2|openclaw) names="$names openclaw" ;;
        3|opencode) names="$names opencode" ;;
        4|crewai)   names="$names crewai" ;;
        5|aider)    names="$names aider" ;;
      esac
    done
    echo "      installing:$names"
    # pip agents (hermes, crewai, aider) - ONE pip command
    pip_list=""
    for s in $names; do
      case "$s" in
        hermes) pip_list="$pip_list hermes-agent" ;;
        crewai) pip_list="$pip_list crewai" ;;
        aider)  pip_list="$pip_list aider-chat" ;;
      esac
    done
    if [ -n "$pip_list" ]; then
      if [ -x "$PIP" ]; then
        echo "      installing:$pip_list into the PC work venv (5-15 min, then copied)..."
        "$WORK_VENV/bin/pip" install --retries 20 --timeout 90 --prefer-binary $pip_list 2>/dev/null && \
          { echo "      ok - copying to the stick..."; \
            if command -v rsync >/dev/null 2>&1; then rsync -a --delete "$WORK_VENV/" "$STICK_VENV/"; else cp -a "$WORK_VENV/." "$STICK_VENV/"; fi; \
            echo "      ok (pip agents on the stick)"; } || \
          echo "      ⚠ pip install failed (network?) - re-run when internet is stable"
      else
        echo "      ⚠ PC work venv not found - re-run the build from step [2/6]"
      fi
    fi
    # npm agents (openclaw, opencode)
    for n in openclaw opencode; do
      if echo "$names" | grep -qw "$n"; then
        pkg="openclaw@latest"; [ "$n" = "opencode" ] && pkg="opencode-ai"
        mkdir -p "$USB/council-data/$n"
        if command -v npm >/dev/null 2>&1; then
          WORK_AGENT="$WORK_ROOT/tools/$n"
          echo "      installing $n on the PC (npm, then copied - FAT-safe)..."
          npm install --prefix "$WORK_AGENT" --no-audit --no-fund "$pkg" >/dev/null 2>&1 && \
            { echo "      ok - copying to the stick..."; \
              mkdir -p "$USB/CouncilKey-Os/tools/$n"; \
              if command -v rsync >/dev/null 2>&1; then rsync -a --delete "$WORK_AGENT/" "$USB/CouncilKey-Os/tools/$n/"; else cp -a "$WORK_AGENT/." "$USB/CouncilKey-Os/tools/$n/"; fi; \
              echo "      ok ($n CLI on the stick)"; } || \
            echo "      ⚠ npm install of $n failed (network?) - re-run when internet is stable"
        else
          echo "      ⚠ npm not found - $n will use the host install"
        fi
      fi
    done
  fi

  # verify what actually landed ON THE STICK (not the PC)
  echo ""
  echo "  agents actually on the stick:"
  for n in hermes openclaw opencode crewai aider; do
    ok=0
    case "$n" in
      hermes)   [ -x "$USB/CouncilKey-Os/.venv/bin/hermes" ] && ok=1; [ -x "$USB/CouncilKey-Os/.venv/Scripts/hermes.exe" ] && ok=1 ;;
      crewai)   [ -x "$USB/CouncilKey-Os/.venv/bin/crewai" ] && ok=1; [ -x "$USB/CouncilKey-Os/.venv/Scripts/crewai.exe" ] && ok=1 ;;
      aider)    [ -x "$USB/CouncilKey-Os/.venv/bin/aider" ] && ok=1; [ -x "$USB/CouncilKey-Os/.venv/Scripts/aider.exe" ] && ok=1 ;;
      openclaw) [ -d "$USB/CouncilKey-Os/tools/openclaw/node_modules/.bin" ] && ok=1 ;;
      opencode) [ -d "$USB/CouncilKey-Os/tools/opencode/node_modules/.bin" ] && ok=1 ;;
    esac
    if [ "$ok" -eq 1 ]; then
      echo "    ✅ $n  (on the stick)"
    else
      if echo "$names" | grep -qw "$n"; then
        echo "    ❌ $n  FAILED to install - re-run with --agents $n when internet is stable"
      else
        echo "    ⚪ $n  (not selected - add later with --agents $n)"
      fi
    fi
  done
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
rem OpenClaw resolves its workspace from the CONFIG FILE first (env vars are only
rem a fallback) - so make sure the stick config exists with the stick workspace.
if not exist "%OPENCLAW_CONFIG_PATH%" (
  powershell -NoProfile -Command "$ws='%STICK%council-data\openclaw\workspace'; $cfg=[ordered]@{agents=@{defaults=@{workspace=$ws}}}; ($cfg|ConvertTo-Json -Depth 5) | Set-Content -Encoding ASCII '%OPENCLAW_CONFIG_PATH%'"
)
echo   Workspace: %OPENCLAW_WORKSPACE_DIR%
if exist "%STICK%CouncilKey-Os\tools\openclaw\node_modules\.bin\openclaw.cmd" (
  echo   Running OpenClaw FROM THE STICK.
  "%STICK%CouncilKey-Os\tools\openclaw\node_modules\.bin\openclaw.cmd" %*
) else (
  echo   [note] OpenClaw is NOT installed on the stick - using the PC copy.
  echo   State and workspace still stay on the stick. To install it on the stick:
  echo     scripts\pendrive-setup.sh %STICK% --agents 2
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
# OpenClaw resolves its workspace from the CONFIG FILE first (env vars are
# only a fallback) - make sure the stick config exists with the stick workspace.
if [ ! -f "$OPENCLAW_CONFIG_PATH" ]; then
  cat > "$OPENCLAW_CONFIG_PATH" <<CFGEOF
{
  "agents": {
    "defaults": {
      "workspace": "$OPENCLAW_WORKSPACE_DIR"
    }
  }
}
CFGEOF
fi
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

cat > "$USB/RUN-OPENCODE.bat" <<'EOF'
@echo off
rem RUN-OPENCODE.bat - OpenCode from the pendrive (Windows) - NO Docker needed
rem OpenCode runs locally: terminal, file editing and web tools on this PC.
rem State and config stay on the stick (council-data\opencode).
setlocal
set "STICK=%~dp0"
set "OPENCODE_CONFIG=%STICK%council-data\opencode\opencode.json"
set "XDG_CONFIG_HOME=%STICK%council-data\opencode\config"
set "XDG_DATA_HOME=%STICK%council-data\opencode\data"
if not exist "%STICK%council-data\opencode" mkdir "%STICK%council-data\opencode"

rem 1. point OpenCode at the provider key stored in the encrypted vault
call "%~dp0CouncilKey-Os\councilkey.bat" agents configure opencode
if errorlevel 1 (
  echo [error] no API key configured yet.
  echo   Run once:  councilkey.bat setup   (choose OpenAI / OpenRouter / Gemini / Anthropic)
  pause
  exit /b 1
)
for /f "delims=" %%K in ('"%~dp0CouncilKey-Os\councilkey.bat" key show OPENROUTER_API_KEY 2^>nul') do set "OPENROUTER_API_KEY=%%K"
for /f "delims=" %%K in ('"%~dp0CouncilKey-Os\councilkey.bat" key show OPENAI_API_KEY 2^>nul') do set "OPENAI_API_KEY=%%K"
for /f "delims=" %%K in ('"%~dp0CouncilKey-Os\councilkey.bat" key show GEMINI_API_KEY 2^>nul') do set "GEMINI_API_KEY=%%K"
for /f "delims=" %%K in ('"%~dp0CouncilKey-Os\councilkey.bat" key show ANTHROPIC_API_KEY 2^>nul') do set "ANTHROPIC_API_KEY=%%K"

rem 2. run opencode (from the stick if installed there, else the PC install)
if exist "%STICK%CouncilKey-Os\tools\opencode\node_modules\.bin\opencode.cmd" (
  "%STICK%CouncilKey-Os\tools\opencode\node_modules\.bin\opencode.cmd" %*
) else (
  opencode %*
)
endlocal
EOF

cat > "$USB/run-opencode.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
export OPENCODE_CONFIG="$STICK/council-data/opencode/opencode.json"
export XDG_CONFIG_HOME="$STICK/council-data/opencode/config"
export XDG_DATA_HOME="$STICK/council-data/opencode/data"
mkdir -p "$STICK/council-data/opencode"
"$STICK/CouncilKey-Os/councilkey" agents configure opencode
export OPENROUTER_API_KEY="$("$STICK/CouncilKey-Os/councilkey" key show OPENROUTER_API_KEY 2>/dev/null || true)"
export OPENAI_API_KEY="$("$STICK/CouncilKey-Os/councilkey" key show OPENAI_API_KEY 2>/dev/null || true)"
export GEMINI_API_KEY="$("$STICK/CouncilKey-Os/councilkey" key show GEMINI_API_KEY 2>/dev/null || true)"
export ANTHROPIC_API_KEY="$("$STICK/CouncilKey-Os/councilkey" key show ANTHROPIC_API_KEY 2>/dev/null || true)"
echo "Config: $OPENCODE_CONFIG"
exec opencode "$@"
EOF

chmod +x "$USB"/run-*.sh
echo "      ok (launchers: RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-OPENCODE)"


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
echo   6) OpenCode  (local agent - no Docker)
echo   0) Quit
echo ==============================================
set /p choice="Choose (A/1-6/0): "
if /i "%choice%"=="A" goto all
if "%choice%"=="1" goto dash
if "%choice%"=="2" goto oc
if "%choice%"=="3" goto hermes
if "%choice%"=="4" goto crewai
if "%choice%"=="5" goto aider
if "%choice%"=="6" goto opencode
if "%choice%"=="0" exit /b 0
goto menu
:all
start "Council Dashboard" cmd /c "%~dp0START.bat"
start "OpenClaw" cmd /c "%~dp0RUN-OPENCLAW.bat"
start "Hermes" cmd /c "%~dp0RUN-HERMES.bat"
start "CrewAI" cmd /c "%~dp0RUN-CREWAI.bat"
start "Aider" cmd /c "%~dp0RUN-AIDER.bat"
start "OpenCode" cmd /c "%~dp0RUN-OPENCODE.bat"
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
:opencode
call "%~dp0RUN-OPENCODE.bat"
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
echo "  6) OpenCode  (local agent - no Docker)"
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
    bash "$STICK/run-opencode.sh" &
    ;;
  1) bash "$STICK/start.sh" ;;
  2) bash "$STICK/run-openclaw.sh" ;;
  3) bash "$STICK/run-hermes.sh" ;;
  4) bash "$STICK/run-crewai.sh" ;;
  5) bash "$STICK/run-aider.sh" ;;
  6) bash "$STICK/run-opencode.sh" ;;
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
for launcher in run-openclaw.sh run-hermes.sh run-crewai.sh run-aider.sh run-opencode.sh; do
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
  Python environment, and the agents you picked (Hermes, OpenClaw, OpenCode,
  CrewAI, Aider). OpenCode is the builder/review agent - terminal, file
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
    RUN-OPENCODE.bat   OpenCode (local)  LAUNCH-ALL.bat   everything

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
echo "   Agents:     RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-OPENCODE (.bat)"
echo "               or run-*.sh on Linux - ALL on the stick, data stays on the stick"
echo "   Data stays on the stick: $USB/council-data"
echo "=============================================="
