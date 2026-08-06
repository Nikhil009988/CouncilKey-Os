@echo off
rem councilkey.bat - run the councilkey CLI from the project venv (Windows).
rem   Usage:  councilkey.bat setup
rem           councilkey.bat serve
rem           councilkey.bat ask "plan a trip"
rem   (or use the full path:  .\.venv\Scripts\councilkey.exe)
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\councilkey.exe" (
  echo [error] project not set up yet - run:  scripts\setup.ps1
  exit /b 1
)
"%ROOT%.venv\Scripts\councilkey.exe" %*
endlocal
