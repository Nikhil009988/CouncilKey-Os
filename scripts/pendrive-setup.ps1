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
  [switch]$NoAgents,
  [switch]$Check,
  [string]$Agents = ""
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
Write-Host " CouncilKey-Os pendrive setup v1.22.2"
Write-Host "  - ASKS which agents to install (nothing automatic)"
Write-Host "  - use -Check first to inspect everything"
Write-Host " Target: $Path"
Write-Host "=============================================="

function Test-Net([string]$HostName) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $t = $c.ConnectAsync($HostName, 443)
    if ($t.Wait(3000) -and $c.Connected) { $c.Close(); return $true }
  } catch {}
  return $false
}


$Dest = Join-Path $Path "CouncilKey-Os"
  $StickPip = Join-Path $Dest ".venv\Scripts\pip.exe"

# ---- CHECK MODE: see everything first, install NOTHING ----
if ($Check) {
  Write-Host ""
  Write-Host "  == Pre-install check (nothing installed) =="
  Write-Host "  stick venv      : $(if (Test-Path $StickPip) { 'ready' } else { 'MISSING - run without -Check first to build' })"
  Write-Host "  python (PC)     : $(if (Get-Command python -ErrorAction SilentlyContinue) { 'ok' } else { 'missing (install Python 3.11+)' })"
  Write-Host "  npm (PC)        : $(if (Get-Command npm -ErrorAction SilentlyContinue) { 'ok' } else { 'missing (OpenClaw/OpenCode need it)' })"
  Write-Host "  internet PyPI   : $(if (Test-Net 'pypi.org') { 'reachable' } else { 'NOT reachable - pip agents will fail' })"
  Write-Host "  internet npmjs  : $(if (Test-Net 'registry.npmjs.org') { 'reachable' } else { 'NOT reachable - npm agents will fail' })"
  if (Test-Path $StickPip) {
    $have = @(& $StickPip list 2>$null | Select-String -Pattern 'hermes-agent|crewai|aider-chat' | ForEach-Object { $_.Line.Split(' ')[0] })
    foreach ($n in @('openclaw', 'opencode')) {
      if (Test-Path (Join-Path $Dest "tools\$n\node_modules\.bin")) { $have += $n }
    }
    Write-Host "  already on stick: $(if ($have) { $have -join ', ' } else { 'none yet' })"
  }
  Write-Host ""
  Write-Host "  Choose what to install, then re-run:"
  Write-Host "    .\scripts\pendrive-setup.ps1 -Path $Path -Agents 1,3,5   (or run without -Agents to pick interactively)"
  return 0
}


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

# ---- choose agents ----
New-Item -ItemType Directory -Force -Path (Join-Path $Path "council-data\agents") | Out-Null
$Selected = @()
if ($NoAgents) {
  Write-Host "      skipped agent installs (-NoAgents) - launchers are still written"
} else {
  if ($Agents) {
    foreach ($part in ($Agents -split ',')) {
      $part = $part.Trim().ToLower()
      if ($AgentMap.ContainsKey($part)) { $Selected += $AgentMap[$part] }
    }
  } else {
    Write-Host ""
    Write-Host "  Which agents do you want ON the stick? (nothing is installed without your choice)"
    Write-Host "    1) Hermes    (pip)     2) OpenClaw  (npm)     3) OpenCode (npm)"
    Write-Host "    4) CrewAI    (pip)     5) Aider     (pip)"
    Write-Host "    A) All 5    0) None"
    $ans = Read-Host "    Pick (e.g. 1,3,5 or A or 0)"
    $ans = $ans.Trim().ToLower()
    if ($ans -in @('a', 'all')) { $Selected = $AgentNames }
    elseif ($ans -in @('', '0', 'none')) { $Selected = @() }
    else {
      foreach ($part in ($ans -split ',')) {
        $part = $part.Trim()
        if ($AgentMap.ContainsKey($part)) { $Selected += $AgentMap[$part] }
      }
    }
  }
  if ($Selected.Count -eq 0) {
    Write-Host "      no agents selected - launchers are still written (install later with -Agents)"
  } else {
    Write-Host "      installing: $($Selected -join ', ')"
    # pip agents (hermes, crewai, aider) - ONE pip command
    $PipSel = @($Selected | Where-Object { $_ -in @('hermes', 'crewai', 'aider') })
    if ($PipSel.Count -gt 0) {
      $PipPkgs = @()
      if ('hermes' -in $PipSel) { $PipPkgs += 'hermes-agent' }
      if ('crewai' -in $PipSel) { $PipPkgs += 'crewai' }
      if ('aider' -in $PipSel)  { $PipPkgs += 'aider-chat' }
      if (Test-Path $StickPip) {
        Write-Host "      installing $($PipPkgs -join ', ') into the stick venv (can take 5-15 min)..."
        & $StickPip install --retries 20 --timeout 90 --prefer-binary @PipPkgs | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Host "      ok ($($PipSel -join ' + ') on the stick)" }
        else { Write-Host "      ⚠ pip install failed (network?) - re-run when internet is stable" }
      } else {
        Write-Host "      ⚠ stick venv not found"
      }
    }
    # npm agents (openclaw, opencode)
    foreach ($n in @('openclaw', 'opencode')) {
      if ($Selected -contains $n) {
        $pkg = if ($n -eq 'openclaw') { 'openclaw@latest' } else { 'opencode-ai' }
        New-Item -ItemType Directory -Force -Path (Join-Path $Path "council-data\$n") | Out-Null
        if (Get-Command npm -ErrorAction SilentlyContinue) {
          Write-Host "      installing $n onto the stick (npm)..."
          & npm install --prefix (Join-Path $Dest "tools\$n") --no-audit --no-fund $pkg | Out-Null
          if ($LASTEXITCODE -eq 0) { Write-Host "      ok ($n CLI on the stick)" }
          else { Write-Host "      ⚠ npm install of $n failed" }
        } else {
          Write-Host "      ⚠ npm not found - $n will use the host install"
        }
      }
    }
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

$OPENCODE_BAT = @"
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
"@
Set-Content -Encoding ASCII (Join-Path $Path "RUN-OPENCODE.bat") $OPENCODE_BAT

Write-Host "      ok (launchers: RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-OPENCODE)"

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
"@ | Set-Content -Encoding ASCII (Join-Path $Path "AGENTS.bat")

# --- README on the stick ---
@"
==============================================
 CouncilKey-Os - PENDRAVE GUIDE (read me)
==============================================

WHAT YOU HAVE
  This stick contains the whole CouncilKey-Os: the app, a portable
  Python environment, and the agents you picked (Hermes, OpenClaw, OpenCode,
  CrewAI, Aider). OpenCode is the builder/review agent - terminal, file
  editing and web tools that run locally on your PC: NO Docker needed.
  ALL data - journal, memory, API keys, agent workspaces - lives on
  this stick in the "council-data" folder.

START ANY AGENT OR EVERYTHING AT ONCE
  Windows:  double-click AGENTS.bat  -> menu: A = ALL, 1-6 = one agent
  Linux:    bash agents-menu.sh
  Or directly:
    START.bat          dashboard (council chat: 3 agents + vote)
    RUN-OPENCLAW.bat   OpenClaw      RUN-HERMES.bat   Hermes
    RUN-CREWAI.bat     CrewAI        RUN-AIDER.bat    Aider
    RUN-OPENCODE.bat   OpenCode (local, no Docker)

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
Write-Host "   Agents:            RUN-OPENCLAW / RUN-HERMES / RUN-CREWAI / RUN-AIDER / RUN-OPENCODE (.bat)"
Write-Host "   Data stays on the stick: $Path\council-data"
Write-Host "=============================================="
