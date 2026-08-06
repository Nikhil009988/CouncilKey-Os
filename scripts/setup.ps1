# setup.ps1 - One-command setup for CouncilKey-Os on Windows (PowerShell).
#   [1] Python venv + CouncilKey-Os
#   [2] INTERACTIVE WIZARD (councilkey setup):
#       - local LLM (Ollama via winget + qwen2.5:3b)
#       - model provider + API keys (stored encrypted)
#       - optional external agents (official installers)
#       - tests + verify
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#   ./scripts/setup.ps1 -NoAgents      # wizard, skip external agents
#   ./scripts/setup.ps1 -NoLlm         # wizard, skip the local LLM
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
Write-Host "[1/2] Installing CouncilKey-Os..."
if (-not (Test-Path "$ROOT\.venv")) {
  python -m venv "$ROOT\.venv"
}
& "$ROOT\.venv\Scripts\pip.exe" install -q -e "$ROOT[dev]"
Write-Host "      ok - 'councilkey' CLI ready"

# 2. Interactive wizard
$WizardArgs = @()
if ($NoAgents) { $WizardArgs += "--no-agents" }
if ($NoLlm) { $WizardArgs += "--no-llm" }
if ($SkipTests) { $WizardArgs += "--skip-tests" }
if ($NoLlm) {
  & "$ROOT\.venv\Scripts\councilkey.exe" setup @WizardArgs
} else {
  # interactive prompts need a real console; run the wizard directly
  & "$ROOT\.venv\Scripts\councilkey.exe" setup @WizardArgs
}

Write-Host ""
Write-Host "=============================================="
Write-Host " ✅ Setup complete"
Write-Host ""
Write-Host "   Start the dashboard:   .\.venv\Scripts\councilkey.exe serve"
Write-Host "   Open:                  http://localhost:8443"
Write-Host "   Agent status:          councilkey agents status"
Write-Host "=============================================="
