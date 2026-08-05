@echo off
setlocal
if "%COUNCIL_HOME%"=="" set COUNCIL_HOME=%LOCALAPPDATA%\CouncilKey
if "%COUNCIL_HOST%"=="" set COUNCIL_HOST=0.0.0.0
if "%COUNCIL_PORT%"=="" set COUNCIL_PORT=8443
python -m uvicorn council.orchestrator.main:app --host "%COUNCIL_HOST%" --port "%COUNCIL_PORT%"
endlocal
