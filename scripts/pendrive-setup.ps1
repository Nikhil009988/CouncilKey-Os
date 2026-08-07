# pendrive-setup.ps1 - ONE command that sets up EVERYTHING on a USB stick (Windows).
#
#   powershell -ExecutionPolicy Bypass -File scripts\pendrive-setup.ps1 -Path E:\
#   or:  .\scripts\pendrive-setup.ps1 -Path E:\ -Wizard
#
# Copies the project + creates a portable venv ON the stick, writes
# START.bat (double-click to start on any Windows PC) and autorun.inf.
param(
  [Parameter(Mandatory = $true)][string]$Path,
  [switch]$Wizard,
  [switch]$NoAgents
)
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path $Path)) {
  Write-Host "❌ $Path is not a directory - mount your pendrive first."
  Write-Host ""
  Write-Host "   Available drives:"
  Get-PSDrive -PSProvider FileSystem | ForEach-Object {
    Write-Host "     $($_.Name):\  ($($_.Root))"
  }
  Write-Host ""
  Write-Host "   Plug in the pendrive, find its letter above, then re-run:"
  Write-Host "     .\scripts\pendrive-setup.ps1 -Path <letter>:\ -Wizard"
  exit 1
}

Write-Host "=============================================="
Write-Host " CouncilKey-Os pendrive setup (Windows)"
Write-Host " Target: $Path"
Write-Host "=============================================="

# 1. copy the project (no git history / heavy junk)
Write-Host ""
Write-Host "[1/5] Copying CouncilKey-Os to the pendrive..."
$Dest = Join-Path $Path "CouncilKey-Os"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Get-ChildItem $ROOT -Force | Where-Object {
  $_.Name -notin @(".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "tools", "node_modules")
} | ForEach-Object {
  Copy-Item -Recurse -Force $_.FullName (Join-Path $Dest $_.Name)
}
Write-Host "      ok"

# 2. portable Python venv ON the stick
Write-Host "[2/5] Creating a portable Python environment ON the stick..."
if (-not (Test-Path "$Dest\.venv\Scripts\python.exe")) {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ python not found on this PC - install Python 3.11+ from https://python.org first"
    exit 1
  }
  python -m venv "$Dest\.venv"
}
& "$Dest\.venv\Scripts\pip.exe" install -q -e $Dest
Write-Host "      ok"

# 3. data dir on the stick
Write-Host "[3/5] Configuring the stick as the council home..."
New-Item -ItemType Directory -Force -Path (Join-Path $Path "council-data") | Out-Null
Write-Host "      ok (data dir: $Path\council-data)"

# 4. START.bat launcher (double-click on any Windows PC)
Write-Host "[4/5] Writing START.bat..."
@"
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
"@ | Set-Content -Encoding ASCII (Join-Path $Path "START.bat")
Write-Host "      ok"

# 5. ALL agents on the stick
Write-Host "[5/7] Installing the agents ONTO the stick (everything stays on the stick)..."
if ($NoAgents) {
  Write-Host "      skipped agent installs (-NoAgents) - launchers are still written"
} else {
  New-Item -ItemType Directory -Force -Path (Join-Path $Path "council-data\agents") | Out-Null

  # Python agents into the stick venv (hermes, crewai, aider)
  $StickPip = Join-Path $Dest ".venv\Scripts\pip.exe"
  if (Test-Path $StickPip) {
    Write-Host "      installing hermes-agent, crewai, aider-chat into the stick venv (one command, can take a few minutes)..."
    & $StickPip install -q hermes-agent crewai aider-chat | Out-Null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "      ok (hermes + crewai + aider on the stick)"
    } else {
      Write-Host "      ⚠ pip install of agents failed - re-run on a machine with internet"
    }
  } else {
    Write-Host "      ⚠ stick venv not found - agents skipped"
  }

  # OpenClaw via npm into the stick
  Write-Host "      installing openclaw onto the stick (npm)..."
  New-Item -ItemType Directory -Force -Path (Join-Path $Path "council-data\openclaw") | Out-Null
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    & npm install --prefix (Join-Path $Dest "tools\openclaw") --no-audit --no-fund openclaw@latest | Out-Null
    Write-Host "      ok (openclaw CLI on the stick)"
  } else {
    Write-Host "      ⚠ npm not found - openclaw will use the host install"
  }

  # Codex CLI via npm into the stick (local agent - no Docker)
  Write-Host "      installing codex onto the stick (npm)..."
  New-Item -ItemType Directory -Force -Path (Join-Path $Path "council-data\codex") | Out-Null
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    & npm install --prefix (Join-Path $Dest "tools\codex") --no-audit --no-fund @openai/codex | Out-Null
    Write-Host "      ok (codex CLI on the stick)"
  } else {
    Write-Host "      ⚠ npm not found - codex will use the host install"
  }
}

# launchers - always written
$OPENCLAW_BAT = @"
@echo off
rem RUN-OPENCLAW.bat - OpenClaw from the pendrive (Windows)
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
"@
Set-Content -Encoding ASCII (Join-Path $Path "RUN-OPENCLAW.bat") $OPENCLAW_BAT

$HERMES_BAT = @"
@echo off
rem RUN-HERMES.bat - Hermes from the pendrive (Windows)
setlocal
set "STICK=%~dp0"
set "HERMES_HOME=%STICK%council-data\agents\hermes"
if exist "%STICK%CouncilKey-Os\.venv\Scripts\hermes.exe" (
  "%STICK%CouncilKey-Os\.venv\Scripts\hermes.exe" %*
) else (
  echo [error] hermes not on the stick - rebuild the stick with internet
  pause
)
endlocal
"@
Set-Content -Encoding ASCII (Join-Path $Path "RUN-HERMES.bat") $HERMES_BAT

$CREWAI_BAT = @"
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
"@
Set-Content -Encoding ASCII (Join-Path $Path "RUN-CREWAI.bat") $CREWAI_BAT

$AIDER_BAT = @"
@echo off
rem RUN-AIDER.bat - Aider from the pendrive (Windows)
setlocal
set "STICK=%~dp0"
if exist "%STICK%CouncilKey-Os\.venv\Scripts\aider.exe" (
  "%STICK%CouncilKey-Os\.venv\Scripts\aider.exe" %*
) else (
  echo [error] aider not on the stick - rebuild the stick with internet
  pause
)
endlocal
"@
Set-Content -Encoding ASCII (Join-Path $Path "RUN-AIDER.bat") $AIDER_BAT

$CODEX_BAT = @"
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
"@
Set-Content -Encoding ASCII (Join-Path $Path "RUN-CODEX.bat") $CODEX_BAT

Write-Host "      ok (launchers: RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-CODEX)"

# 6. autorun.inf + optional wizard

# 7. session mode + agent menu + stick README
Write-Host "[7/7] Writing session-mode, agent menu and launch-all launchers..."

# --- session mode (clone to PC, memory on stick, wipe on end) ---
@"
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
copy /y "%ROOT%\VERSION" "%SESSION%\" >nul
copy /y "%ROOT%\pyproject.toml" "%SESSION%\" >nul

echo   dashboard: http://localhost:8443  (close this window to stop)
echo.
cd /d "%SESSION%"
"%ROOT%\.venv\Scripts\python.exe" -m uvicorn council.orchestrator.main:app --host 0.0.0.0 --port 8443
endlocal
"@ | Set-Content -Encoding ASCII (Join-Path $Path "START-SESSION.bat")

@"
@echo off
rem END-SESSION.bat - stop the session and WIPE it from this PC
set "SESSION=%TEMP%\councilkey-session"
if exist "%SESSION%" rmdir /s /q "%SESSION%"
echo == session ended ==
echo   PC copy deleted - nothing left on this PC.
echo   Memory is safe on the stick: council-data\
pause
"@ | Set-Content -Encoding ASCII (Join-Path $Path "END-SESSION.bat")

# --- agent menu: any agent or all at once ---
@"
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
"@ | Set-Content -Encoding ASCII (Join-Path $Path "AGENTS.bat")

# --- README on the stick ---
@"
==============================================
 CouncilKey-Os - PENDRAVE GUIDE (read me)
==============================================

WHAT YOU HAVE
  This stick contains the whole CouncilKey-Os: the app, a portable
  Python environment, and all 5 agents (Hermes, OpenClaw, Codex,
  CrewAI, Aider). Codex replaced Agent Zero - it gives you the same
  builder/review powers (terminal, file editing, web) but runs
  locally on your PC: NO Docker needed.
  ALL data - journal, memory, API keys, agent workspaces - lives on
  this stick in the "council-data" folder.

START ANY AGENT OR EVERYTHING AT ONCE
  Windows:  double-click AGENTS.bat  -> menu: A = ALL, 1-6 = one agent
  Linux:    bash agents-menu.sh
  Or directly:
    START.bat          dashboard (council chat: 3 agents + vote)
    RUN-OPENCLAW.bat   OpenClaw      RUN-HERMES.bat   Hermes
    RUN-CREWAI.bat     CrewAI        RUN-AIDER.bat    Aider
    RUN-CODEX.bat      Codex (local, no Docker)

SESSION MODE (clone to PC, memory on stick, no traces)
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
"@ | Set-Content -Encoding ASCII (Join-Path $Path "PENDRIVE-README.txt")

Write-Host "      ok (session mode, agent menu, PENDRIVE-README.txt)"

Write-Host "[6/7] Writing autorun.inf..."
@"
[autorun]
open=START.bat
label=CouncilKey-Os
action=Start CouncilKey-Os
shell\start=Start CouncilKey-Os
shell\start\command=START.bat
"@ | Set-Content -Encoding ASCII (Join-Path $Path "autorun.inf")

if ($Wizard) {
  Write-Host "  running the interactive wizard (API key + agents)..."
  $env:COUNCIL_HOME = Join-Path $Path "council-data"
  & "$Dest\.venv\Scripts\councilkey.exe" setup
} else {
  Write-Host "  (run the wizard anytime: $env:COUNCIL_HOME = '$Path\council-data'; $Dest\.venv\Scripts\councilkey.exe setup)"
}

Write-Host ""
Write-Host "=============================================="
Write-Host " ✅ Pendrive ready!"
Write-Host ""
Write-Host "   On any Windows PC: plug in -> double-click START.bat"
Write-Host "   Dashboard:         http://localhost:8443"
Write-Host "   Agents:            RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-CODEX (.bat)"
Write-Host "   Data stays on the stick: $Path\council-data"
Write-Host "=============================================="
