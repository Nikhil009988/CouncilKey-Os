# start.ps1 - Start CouncilKey-Os dashboard on Windows.
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path "$ROOT\.venv\Scripts\python.exe")) {
  Write-Host "❌ not set up yet - run:  .\scripts\setup.ps1"
  exit 1
}

# Optional: try to start the local LLM if it's installed but not running
if (Get-Command ollama -ErrorAction SilentlyContinue) {
  try { $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 }
  catch {
    Write-Host "starting ollama (local LLM)..."
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
  }
}

$env:COUNCIL_HOME = if ($env:COUNCIL_HOME) { $env:COUNCIL_HOME } else { "$env:LOCALAPPDATA\CouncilKey" }
Write-Host "dashboard: http://localhost:8443   (Ctrl+C to stop)"
& "$ROOT\.venv\Scripts\python.exe" -m uvicorn council.orchestrator.main:app --host 0.0.0.0 --port 8443
