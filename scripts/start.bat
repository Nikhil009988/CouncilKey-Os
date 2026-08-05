@echo off
setlocal
set COUNCIL_HOME=%COUNCIL_HOME%
set COUNCIL_HOST=%COUNCIL_HOST:0.0.0.0%
set COUNCIL_PORT=%COUNCIL_PORT:8443%
python -m uvicorn council.orchestrator.main:app --host "%COUNCIL_HOST%" --port "%COUNCIL_PORT%"
endlocal
