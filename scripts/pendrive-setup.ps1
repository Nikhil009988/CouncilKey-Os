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
  Write-Host "❌ $Path is not a directory - mount your pendrive first"
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
Write-Host "[5/6] Installing the agents ONTO the stick (everything stays on the stick)..."
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
}

# launchers - always written
$OPENCLAW_BAT = @"
@echo off
rem RUN-OPENCLAW.bat - OpenClaw from the pendrive (Windows)
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

$AZ_BAT = @"
@echo off
rem RUN-AGENT-ZERO.bat - Agent Zero from the pendrive (Windows)
rem Needs Python 3.12+. State stays on the stick.
setlocal
set "STICK=%~dp0"
if exist "%STICK%CouncilKey-Os\tools\agent-zero\.venv\Scripts\python.exe" (
  pushd "%STICK%CouncilKey-Os\tools\agent-zero"
  "%STICK%CouncilKey-Os\tools\agent-zero\.venv\Scripts\python.exe" agent.py %*
  popd
) else (
  echo [error] agent-zero not set up on the stick.
  echo   On a PC with Python 3.12+:  cd tools\agent-zero ^&^& python -m venv .venv
  echo   then: .venv\Scripts\pip install -r requirements.txt
  pause
)
endlocal
"@
Set-Content -Encoding ASCII (Join-Path $Path "RUN-AGENT-ZERO.bat") $AZ_BAT

Write-Host "      ok (launchers: RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-AGENT-ZERO)"

# 6. autorun.inf + optional wizard

Write-Host "[6/6] Writing autorun.inf..."
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
Write-Host "   Agents:            RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-AGENT-ZERO (.bat)"
Write-Host "   Data stays on the stick: $Path\council-data"
Write-Host "=============================================="
