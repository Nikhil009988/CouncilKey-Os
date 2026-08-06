# pendrive-setup.ps1 - ONE command that sets up EVERYTHING on a USB stick (Windows).
#
#   powershell -ExecutionPolicy Bypass -File scripts\pendrive-setup.ps1 -Path E:\
#   or:  .\scripts\pendrive-setup.ps1 -Path E:\ -Wizard
#
# Copies the project + creates a portable venv ON the stick, writes
# START.bat (double-click to start on any Windows PC) and autorun.inf.
param(
  [Parameter(Mandatory = $true)][string]$Path,
  [switch]$Wizard
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

# 5. autorun.inf + optional wizard
Write-Host "[5/5] Writing autorun.inf..."
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
Write-Host "   Data stays on the stick: $Path\council-data"
Write-Host "=============================================="
