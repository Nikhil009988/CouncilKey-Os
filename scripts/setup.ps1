# setup.ps1 - One-command setup for CouncilKey-Os on Windows (PowerShell).
#
#   [1] Python venv + CouncilKey-Os
#   [2] INSTALLS EVERYTHING to make the agents run:
#       - all 5 external agents (Hermes, OpenClaw, CrewAI, Aider via their
#         official installers; Codex via npm, no Docker)
#       - the API key (from $env:OPENAI_API_KEY / ANTHROPIC / GEMINI /
#         OPENROUTER, or the interactive wizard)
#       - verifies the council answers
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1         # wizard (asks for key + agents)
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Full   # INSTALL EVERYTHING automatically
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Full -ApiKey sk-...   # + key
param(
  [switch]$Full,
  [switch]$NoAgents,
  [switch]$SkipTests,
  [string]$ApiKey = ""
)
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "=============================================="
Write-Host " CouncilKey-Os setup (Windows)"
Write-Host "=============================================="

# 0. prerequisites with CLEAR messages
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host ""
  Write-Host "❌ Python is not installed or not on PATH."
  Write-Host ""
  Write-Host "   Install it (tick 'Add python.exe to PATH' during install):"
  Write-Host "     https://www.python.org/downloads/"
  Write-Host "   or one command:"
  Write-Host "     winget install Python.Python.3.11"
  Write-Host ""
  Write-Host "   Then open a NEW terminal and re-run this setup."
  exit 1
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host ""
  Write-Host "❌ git is not installed."
  Write-Host "   Install it:  winget install Git.Git"
  Write-Host "   Then open a NEW terminal and re-run this setup."
  exit 1
}

# 1. Python + package
Write-Host ""
Write-Host "[1/3] Installing CouncilKey-Os..."
if (-not (Test-Path "$ROOT\.venv")) {
  python -m venv "$ROOT\.venv"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ could not create the Python environment."
    Write-Host "   Make sure Python 3.11+ is installed (python.org) and re-run."
    exit 1
  }
}
& "$ROOT\.venv\Scripts\pip.exe" install -q -e "$ROOT[dev]"
Write-Host "      ok - 'councilkey' CLI ready"

# 2a. FULL AUTO: install everything without prompts
if ($Full) {
  Write-Host ""
  Write-Host "[2/3] Installing ALL agents automatically (this takes a few minutes)..."
  & "$ROOT\.venv\Scripts\councilkey.exe" agents install
  Write-Host "      agents installed - check with: councilkey agents status"

  # API key: env vars first, then -ApiKey flag
  $KeyEnv = $env:OPENAI_API_KEY
  $Provider = "openai"
  if (-not $KeyEnv) { $KeyEnv = $env:ANTHROPIC_API_KEY; $Provider = "anthropic" }
  if (-not $KeyEnv) { $KeyEnv = $env:GEMINI_API_KEY; $Provider = "gemini" }
  if (-not $KeyEnv) { $KeyEnv = $env:OPENROUTER_API_KEY; $Provider = "openrouter" }
  if (-not $KeyEnv -and $ApiKey) { $KeyEnv = $ApiKey }

  if ($KeyEnv) {
    Write-Host ""
    Write-Host "[2/3] Storing the API key (from env / -ApiKey)..."
    & "$ROOT\.venv\Scripts\councilkey.exe" setup --provider $Provider --api-key $KeyEnv --no-agents --skip-tests --skip-verify
    Write-Host "      ok - key stored encrypted"
  } else {
    Write-Host ""
    Write-Host "      ⚠ no API key found (OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / OPENROUTER_API_KEY env, or -ApiKey)."
    Write-Host "        The agents won't answer until you add one:"
    Write-Host "        .\councilkey.bat setup"
  }
} else {
  # 2b. interactive wizard
  Write-Host ""
  Write-Host "[2/3] Setup wizard..."
  $WizardArgs = @()
  if ($NoAgents) { $WizardArgs += "--no-agents" }
  if ($SkipTests) { $WizardArgs += "--skip-tests" }
  & "$ROOT\.venv\Scripts\councilkey.exe" setup @WizardArgs
}

# 3. verify
if (-not $SkipTests) {
  Write-Host ""
  Write-Host "[3/3] Verifying the council (real ask)..."
  & "$ROOT\.venv\Scripts\councilkey.exe" agents verify
}

Write-Host ""
Write-Host "=============================================="
Write-Host " ✅ Setup complete"
Write-Host ""
Write-Host "   Run the CLI from the repo root:  .\councilkey.bat"
Write-Host "   Start the dashboard:   .\councilkey.bat serve"
Write-Host "   Open:                  http://localhost:8443"
Write-Host "   Agent status:          .\councilkey.bat agents status"
Write-Host "=============================================="
