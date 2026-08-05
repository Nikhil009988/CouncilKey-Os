<#>
.SYNOPSIS
    CouncilKey-Os One-Command Installer for Windows PowerShell
.DESCRIPTION
    Downloads, builds, and installs CouncilKey-Os portable environment to a USB drive.
    Run from PowerShell 5.1+ or PowerShell Core 6+.
.EXAMPLE
    # Install to auto-detected USB drive
    iwr -useb https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/scripts/install.ps1 | iex

    # Install to specific drive letter
    iwr -useb https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/scripts/install.ps1 | iex -DriveLetter E

    # Install to specific path
    iwr -useb https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/scripts/install.ps1 | iex -TargetPath "D:\CouncilKey-Os"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateNotNullOrEmpty()]
    [string]$DriveLetter,

    [Parameter(Mandatory=$false)]
    [ValidateNotNullOrEmpty()]
    [string]$TargetPath,

    [Parameter(Mandatory=$false)]
    [switch]$AutoDetect = $true,

    [Parameter(Mandatory=$false)]
    [ValidateSet('minimal', 'full')]
    [string]$Profile = 'full',

    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild = $false
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Colors
$green  = [ConsoleColor]::Green
$yellow = [ConsoleColor]::Yellow
$cyan   = [ConsoleColor]::Cyan
$red    = [ConsoleColor]::Red
$gray   = [ConsoleColor]::DarkGray

function Write-Status { param($msg) Write-Host "  $msg" -ForegroundColor $cyan }
function Write-Success { param($msg) Write-Host "  ✓ $msg" -ForegroundColor $green }
function Write-Warning { param($msg) Write-Host "  ⚠ $msg" -ForegroundColor $yellow }
function Write-ErrorMsg { param($msg) Write-Host "  ✗ $msg" -ForegroundColor $red }
function Write-Step { param($n, $total, $msg) Write-Host "`n[$n/$total] $msg" -ForegroundColor $yellow }

# Detect USB drive
function Get-USBDrive {
    $drives = Get-WmiObject Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 }
    if ($drives.Count -eq 0) {
        Write-ErrorMsg "No removable USB drives found. Please insert a USB drive (8GB+ recommended)."
        exit 1
    }
    if ($drives.Count -eq 1) { return $drives[0].DeviceID }
    Write-Host "`nMultiple USB drives found:" -ForegroundColor $yellow
    $drives | ForEach-Object { 
        $sizeGB = [math]::Round($_.Size / 1GB, 1)
        $freeGB = [math]::Round($_.FreeSpace / 1GB, 1)
        Write-Host "  $($_.DeviceID)  -  $($_.VolumeName)  -  $freeGB GB free / $sizeGB GB total" -ForegroundColor $gray
    }
    $choice = Read-Host "Select drive letter (e.g., E:)"
    if ($drives.DeviceID -contains $choice) { return $choice }
    Write-ErrorMsg "Invalid selection"
    exit 1
}

# Check prerequisites
function Check-Prereqs {
    Write-Step 1 5 "Checking prerequisites..."
    
    # Git
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Warning "Git not found. Installing via winget..."
        winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
    }
    Write-Success "Git: $(git --version)"

    # Python 3.11+
    $py = @("python", "python3", "py") | ForEach-Object { 
        if (Get-Command $_ -ErrorAction SilentlyContinue) { $_ } 
    } | Select-Object -First 1
    if (-not $py) {
        Write-Warning "Python not found. Installing via winget..."
        winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
        $py = "python"
    }
    $version = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ([version]$version -lt [version]'3.11') {
        Write-ErrorMsg "Python 3.11+ required. Found $version"
        exit 1
    }
    Write-Success "Python: $version ($py)"

    # Node.js (optional, for OpenClaw)
    if (Get-Command node -ErrorAction SilentlyContinue) {
        Write-Success "Node.js: $(node --version)"
    } else {
        Write-Warning "Node.js not found (optional for OpenClaw). Install: winget install OpenJS.NodeJS"
    }
}

# Clone repo
function Clone-Repo {
    Write-Step 2 5 "Cloning CouncilKey-Os..."
    $repoUrl = "https://github.com/Nikhil009988/CouncilKey-Os.git"
    $repoDir = "$env:TEMP\CouncilKey-Os-Install"
    
    if (Test-Path $repoDir) { Remove-Item $repoDir -Recurse -Force }
    
    git clone --depth 1 --branch main $repoUrl $repoDir | Out-Null
    Write-Success "Cloned to $repoDir"
    return $repoDir
}

# Build portable environment
function Build-Portable {
    param($RepoDir)
    
    if ($SkipBuild) {
        Write-Warning "Skipping build (--SkipBuild specified)"
        return
    }
    
    Write-Step 3 5 "Building portable environment (this takes 5-15 minutes)..."
    
    cd $RepoDir
    
    # Step 1: Vendor agents
    Write-Status "Downloading agent sources..."
    bash scripts/build/build-vendor-agents.sh
    Write-Success "Agent sources downloaded"
    
    # Step 2: Build portable venv
    Write-Status "Creating Python environment & installing dependencies..."
    bash scripts/build/build-portable-env.sh
    Write-Success "Portable environment built"
    
    # Verify build
    $buildDir = "$RepoDir\build\portable"
    if (-not (Test-Path "$buildDir\.venv\Scripts\python.exe")) {
        Write-ErrorMsg "Build failed - venv not found"
        exit 1
    }
    Write-Success "Build verified at $buildDir"
    return $buildDir
}

# Deploy to USB
function Deploy-To-USB {
    param($BuildDir, $TargetDrive)
    
    Write-Step 4 5 "Deploying to USB drive $TargetDrive..."
    
    $usbRoot = "$TargetDrive\CouncilKey-Os"
    if (Test-Path $usbRoot) {
        Write-Warning "Target exists, removing..."
        Remove-Item $usbRoot -Recurse -Force
    }
    
    # Copy build output
    Write-Status "Copying files to USB (this may take a minute)..."
    Copy-Item "$BuildDir\*" $usbRoot -Recurse -Force
    Write-Success "Files copied to $usbRoot"
    
    # Create config directories
    $councilHome = "$usbRoot\config\council"
    $dirs = @(
        "$councilHome\hermes\keep", "$councilHome\hermes\cache",
        "$councilHome\openclaw\keep", "$councilHome\openclaw\cache",
        "$councilHome\agent-zero\keep", "$councilHome\agent-zero\cache",
        "$councilHome\shared", "$councilHome\journal", "$councilHome\secrets",
        "$councilHome\council", "$councilHome\lance",
        "$usbRoot\temp"
    )
    foreach ($d in $dirs) {
        if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    }
    
    # Write config.yaml with USB paths
    $config = @"
council:
  mode: "debate"
  agents:
    hermes:
      weight: 1
      timeout: 60
    openclaw:
      weight: 1
      timeout: 60
    agent-zero:
      weight: 1
      timeout: 120
  consensus:
    strategy: "majority"
    min_agreement: 2
"@
    $config | Set-Content -Path "$councilHome\council\council.yaml" -Encoding UTF8
    
    Write-Success "USB configured at $usbRoot"
    return $usbRoot
}

# Create shortcuts
function Create-Shortcuts {
    param($UsbRoot)
    
    Write-Step 5 5 "Creating shortcuts..."
    
    $ws = New-Object -ComObject WScript.Shell
    
    # Desktop shortcut
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcut = $ws.CreateShortcut("$desktop\CouncilKey-Os.lnk")
    $shortcut.TargetPath = "$UsbRoot\start.bat"
    $shortcut.WorkingDirectory = $UsbRoot
    $shortcut.IconLocation = "$UsbRoot\start.bat"
    $shortcut.Save()
    
    # Start Menu shortcut
    $startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
    $shortcut2 = $ws.CreateShortcut("$startMenu\CouncilKey-Os.lnk")
    $shortcut2.TargetPath = "$UsbRoot\start.bat"
    $shortcut2.WorkingDirectory = $UsbRoot
    $shortcut2.Save()
    
    Write-Success "Shortcuts created on Desktop & Start Menu"
}

# Main
Write-Host "`n╔═══════════════════════════════════════════╗" -ForegroundColor $cyan
Write-Host "║   CouncilKey-Os Portable Installer       ║" -ForegroundColor $cyan
Write-Host "║   3 AI Agents • Zero Traces • Offline    ║" -ForegroundColor $cyan
Write-Host "╚═══════════════════════════════════════════╝`n" -ForegroundColor $cyan

# Determine target
if ($TargetPath) {
    $targetDrive = Split-Path -Qualifier $TargetPath
    $usbRoot = $TargetPath
} elseif ($DriveLetter) {
    $targetDrive = $DriveLetter
    $usbRoot = "$DriveLetter\CouncilKey-Os"
} elseif ($AutoDetect) {
    $targetDrive = Get-USBDrive
    $usbRoot = "$targetDrive\CouncilKey-Os"
} else {
    Write-ErrorMsg "Specify -DriveLetter, -TargetPath, or use -AutoDetect"
    exit 1
}

Write-Host "`nTarget: $usbRoot" -ForegroundColor $yellow
$confirm = Read-Host "Continue? (y/N)"
if ($confirm -ne 'y' -and $confirm -ne 'Y') { exit 0 }

try {
    Check-Prereqs
    $repoDir = Clone-Repo
    $buildDir = Build-Portable -RepoDir $repoDir
    $usbRoot = Deploy-To-USB -BuildDir $buildDir -TargetDrive $targetDrive
    Create-Shortcuts -UsbRoot $usbRoot
    
    Write-Host "`n╔═══════════════════════════════════════════╗" -ForegroundColor $green
    Write-Host "║   ✅ Installation Complete!              ║" -ForegroundColor $green
    Write-Host "╚═══════════════════════════════════════════╝`n" -ForegroundColor $green
    
    Write-Host "USB Location: $usbRoot" -ForegroundColor $cyan
    Write-Host "`nTo run CouncilKey-Os:" -ForegroundColor $yellow
    Write-Host "  1. Plug USB into any Windows/Linux/macOS machine" -ForegroundColor $gray
    Write-Host "  2. Double-click start.bat (Windows) or ./start.sh (Linux/macOS)" -ForegroundColor $gray
    Write-Host "  3. Open http://localhost:8444 in browser" -ForegroundColor $gray
    Write-Host "`nFeatures:" -ForegroundColor $yellow
    Write-Host "  • 3 AI Agents (Hermes, OpenClaw, Agent Zero)" -ForegroundColor $gray
    Write-Host "  • Works OFFLINE - zero internet required" -ForegroundColor $gray
    Write-Host "  • Zero traces on host - all data on USB" -ForegroundColor $gray
    Write-Host "  • Works on Windows, Linux, macOS" -ForegroundColor $gray
    
} catch {
    Write-ErrorMsg "Installation failed: $_"
    exit 1
}