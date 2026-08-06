# install.ps1 - One-line installer for CouncilKey-Os on Windows (PowerShell).
#
#   iex (irm https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/install.ps1)
#
# Clones the repo into $HOME\councilkey-os and runs the interactive setup
# wizard (model provider + API key + optional agents).
param(
  [string]$Dest = "$HOME\councilkey-os",
  [switch]$NoAgents,
  [switch]$SkipTests
)
$ErrorActionPreference = "Stop"

Write-Host "== CouncilKey-Os installer (Windows) =="
Write-Host "Installing to: $Dest"

if (Test-Path "$Dest\.git") {
  Write-Host "Repo already present - updating..."
  git -C $Dest pull --ff-only
} else {
  git clone --depth 1 https://github.com/Nikhil009988/CouncilKey-Os.git $Dest
}

# run the full setup (venv + wizard)
$args = @()
if ($NoAgents) { $args += "-NoAgents" }
if ($SkipTests) { $args += "-SkipTests" }
& powershell -ExecutionPolicy Bypass -File "$Dest\scripts\setup.ps1" @args

Write-Host ""
Write-Host "✅ Installed. Next steps:"
Write-Host "  cd $Dest"
Write-Host "  .\councilkey.bat serve      # start the dashboard -> http://localhost:8443"
