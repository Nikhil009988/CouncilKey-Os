# setup.ps1 - One-command setup for CouncilKey-Os on Windows (PowerShell).
#   [1] Python venv + CouncilKey-Os
#   [2] INTERACTIVE WIZARD (councilkey setup):
#       - model provider + API key (stored encrypted in the secrets vault)
#       - optional external agents (official installers)
#       - tests + verify
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#   ./scripts/setup.ps1 -NoAgents      # wizard, skip external agents
param(
  [switch]$NoAgents,
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
if ($SkipTests) { $WizardArgs += "--skip-tests" }
& "$ROOT\.venv\Scripts\councilkey.exe" setup @WizardArgs

Write-Host ""
Write-Host "=============================================="
Write-Host " ✅ Setup complete"
Write-Host ""
Write-Host "   Run the CLI from the repo root:  .\councilkey.bat"
Write-Host "   Start the dashboard:   .\councilkey.bat serve"
Write-Host "   Open:                  http://localhost:8443"
Write-Host "   Agent status:          .\councilkey.bat agents status"
Write-Host "=============================================="
