@echo off
setlocal
rem start.bat - Start CouncilKey-Os dashboard on Windows.
rem   Usage: scripts\start.bat   (or double-click)

set ROOT=%~dp0..

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo [ERROR] Not set up yet. Run setup first:
  echo     powershell -ExecutionPolicy Bypass -File "%ROOT%\scripts\setup.ps1"
  pause
  exit /b 1
)

if "%COUNCIL_HOME%"=="" set COUNCIL_HOME=%LOCALAPPDATA%\CouncilKey
if "%COUNCIL_HOST%"=="" set COUNCIL_HOST=0.0.0.0
if "%COUNCIL_PORT%"=="" set COUNCIL_PORT=8443

echo CouncilKey-Os dashboard: http://localhost:%COUNCIL_PORT%   (Ctrl+C to stop)
"%ROOT%\.venv\Scripts\python.exe" -m uvicorn council.orchestrator.main:app --host "%COUNCIL_HOST%" --port "%COUNCIL_PORT%"
endlocal
