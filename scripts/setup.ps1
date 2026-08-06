# setup.ps1 - One-command setup for CouncilKey-Os on Windows (PowerShell).
#   [1] Python venv + CouncilKey-Os
#   [2] Local LLM (Ollama via winget + qwen2.5:3b) -> council really answers
#   [3] Optional external agents (official installers)
#   [4] tests + verify
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#   ./scripts/setup.ps1 -NoAgents      # skip external agents
#   ./scripts/setup.ps1 -NoLlm         # skip the local LLM
param(
  [switch]$NoAgents,
  [switch]$NoLlm,
  [switch]$SkipTests
)
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "=============================================="
Write-Host " CouncilKey-Os setup (Windows)"
Write-Host "=============================================="

# 1. Python + package
Write-Host ""
Write-Host "[1/5] Installing CouncilKey-Os..."
if (-not (Test-Path "$ROOT\.venv")) {
  python -m venv "$ROOT\.venv"
}
& "$ROOT\.venv\Scripts\pip.exe" install -q -e "$ROOT[dev]"
Write-Host "      ok - 'councilkey' CLI ready"

# 2. Local LLM
if ($NoLlm) {
  Write-Host "[2/5] Skipping local LLM (-NoLlm)"
} else {
  Write-Host "[2/5] Local LLM (Ollama + qwen2.5:3b) - makes the 3 agents answer"
  if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "      ollama already installed"
  } else {
    Write-Host "      installing ollama via winget..."
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    Write-Host "      starting ollama..."
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
  }
  Write-Host "      pulling model qwen2.5:3b (~1.9GB, one-time)..."
  & "$ROOT\.venv\Scripts\councilkey.exe" llm pull qwen2.5:3b
}

# 3. Optional external agents (official installers)
if ($NoAgents) {
  Write-Host "[3/5] Skipping external agents (-NoAgents)"
} else {
  Write-Host "[3/5] External agents (optional, official installers)..."
  & "$ROOT\.venv\Scripts\councilkey.exe" agents install
}

# 4. Tests
if ($SkipTests) {
  Write-Host "[4/5] Skipping tests (-SkipTests)"
} else {
  Write-Host "[4/5] Running the test suite..."
  Push-Location $ROOT
  & "$ROOT\.venv\Scripts\python.exe" -m pytest tests -q
  Pop-Location
}

# 5. Verify
Write-Host ""
Write-Host "[5/5] Verifying the council (real ask)..."
& "$ROOT\.venv\Scripts\councilkey.exe" agents verify

Write-Host ""
Write-Host "=============================================="
Write-Host " ✅ Setup complete"
Write-Host ""
Write-Host "   Start the dashboard:   .\.venv\Scripts\councilkey.exe serve"
Write-Host "   Open:                  http://localhost:8443"
Write-Host "   Agent status:          councilkey agents status"
Write-Host "=============================================="
