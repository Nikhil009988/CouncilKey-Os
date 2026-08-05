#!/usr/bin/env bash
# CouncilKey-Os One-Command Installer for macOS/Linux
# Usage: curl -fsSL https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/scripts/install.sh | bash
#        curl -fsSL https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/scripts/install.sh | bash -s -- /path/to/usb

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

write_step() { echo -e "\n${YELLOW}[$1/$2] $3${NC}"; }
write_success() { echo -e "  ${GREEN}✓${NC} $1"; }
write_warning() { echo -e "  ${YELLOW}⚠${NC} $1"; }
write_error() { echo -e "  ${RED}✗${NC} $1"; }
write_status() { echo -e "  ${CYAN}$1${NC}"; }

REPO_URL="https://github.com/Nikhil009988/CouncilKey-Os.git"
REPO_DIR="/tmp/CouncilKey-Os-Install"
BUILD_DIR="$REPO_DIR/build/portable"
TARGET_PATH="${1:-}"
AUTO_DETECT="${AUTO_DETECT:-true}"
PROFILE="${PROFILE:-full}"
SKIP_BUILD="${SKIP_BUILD:-false}"

echo -e "\n${CYAN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   CouncilKey-Os Portable Installer       ║${NC}"
echo -e "${CYAN}║   3 AI Agents • Zero Traces • Offline    ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}\n"

# Detect USB drive on Linux/macOS
detect_usb() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        diskutil list external physical | grep -E "(external|USB)" | head -5
        echo "Available USB drives:"
        diskutil list external | grep -E "(/dev/disk[0-9]+)" | while read line; do
            disk=$(echo "$line" | awk '{print $1}')
            size=$(diskutil info "$disk" 2>/dev/null | grep "Disk Size" | awk -F: '{print $2}' | xargs)
            echo "  $disk - $size"
        done
        read -p "Enter disk identifier (e.g., /dev/disk4): " DISK
        TARGET=$(diskutil info "$DISK" 2>/dev/null | grep "Mount Point" | awk -F: '{print $2}' | xargs)
        if [[ -z "$TARGET" ]]; then
            echo "Mounting..."
            diskutil mount "$DISK" 2>/dev/null || true
            sleep 2
            TARGET=$(diskutil info "$DISK" 2>/dev/null | grep "Mount Point" | awk -F: '{print $2}' | xargs)
        fi
    else
        # Linux
        lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep -E "(disk|part)" | grep -v "loop"
        echo "Available USB drives:"
        lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep "part" | while read name size type mount; do
            if [[ "$mount" != "" ]]; then
                echo "  $mount ($size)"
            fi
        done
        read -p "Enter mount path (e.g., /media/user/USB): " TARGET
    fi
    
    if [[ ! -d "$TARGET" ]]; then
        echo -e "${RED}Invalid target: $TARGET${NC}"
        exit 1
    fi
    USB_ROOT="$TARGET/CouncilKey-Os"
}

check_prereqs() {
    write_step 1 5 "Checking prerequisites..."
    
    # Git
    if ! command -v git &> /dev/null; then
        write_warning "Git not found. Installing..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install git
        else
            sudo apt-get update && sudo apt-get install -y git
        fi
    fi
    write_success "Git: $(git --version)"
    
    # Python 3.11+
    PYTHON_CMD=$(command -v python3 || command -v python)
    if [[ -z "$PYTHON_CMD" ]]; then
        write_warning "Python not found. Installing..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install python@3.11
        else
            sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv
        fi
        PYTHON_CMD="python3.11"
    fi
    PY_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if (( $(echo "$PY_VERSION < 3.11" | bc -l) )); then
        write_error "Python 3.11+ required. Found $PY_VERSION"
        exit 1
    fi
    write_success "Python: $PY_VERSION ($PYTHON_CMD)"
    
    # Node.js (optional)
    if command -v node &> /dev/null; then
        write_success "Node.js: $(node --version)"
    else
        write_warning "Node.js not found (optional for OpenClaw)"
    fi
}

clone_repo() {
    write_step 2 5 "Cloning CouncilKey-Os..."
    if [[ -d "$REPO_DIR" ]]; then
        rm -rf "$REPO_DIR"
    fi
    git clone --depth 1 --branch main "$REPO_URL" "$REPO_DIR"
    write_success "Cloned to $REPO_DIR"
}

build_portable() {
    if [[ "$SKIP_BUILD" == "true" ]]; then
        write_warning "Skipping build (--skip-build)"
        return
    fi
    
    write_step 3 5 "Building portable environment (5-15 minutes)..."
    cd "$REPO_DIR"
    
    write_status "Downloading agent sources..."
    bash scripts/build/build-vendor-agents.sh
    write_success "Agent sources downloaded"
    
    write_status "Creating Python environment & installing dependencies..."
    bash scripts/build/build-portable-env.sh
    write_success "Portable environment built"
    
    if [[ ! -f "$BUILD_DIR/.venv/bin/python" ]]; then
        write_error "Build failed - venv not found"
        exit 1
    fi
    write_success "Build verified at $BUILD_DIR"
}

deploy_usb() {
    write_step 4 5 "Deploying to $USB_ROOT..."
    
    if [[ -d "$USB_ROOT" ]]; then
        write_warning "Target exists, removing..."
        rm -rf "$USB_ROOT"
    fi
    
    write_status "Copying files to USB..."
    mkdir -p "$USB_ROOT"
    cp -r "$BUILD_DIR"/* "$USB_ROOT/"
    write_success "Files copied to $USB_ROOT"
    
    # Create config directories
    COUNCIL_HOME="$USB_ROOT/config/council"
    mkdir -p "$COUNCIL_HOME"/{hermes/{keep,cache},openclaw/{keep,cache},agent-zero/{keep,cache},shared,journal,secrets,council,lance}
    mkdir -p "$USB_ROOT/temp"
    
    # Write config.yaml
    cat > "$COUNCIL_HOME/council/council.yaml" << EOF
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
EOF
    
    write_success "USB configured at $USB_ROOT"
}

create_shortcuts() {
    write_step 5 5 "Creating launchers..."
    
    # Make start scripts executable
    chmod +x "$USB_ROOT/start.sh"
    chmod +x "$USB_ROOT/start.py"
    
    # Create desktop entry (Linux)
    if [[ "$OSTYPE" != "darwin"* ]] && command -v xdg-desktop-menu &> /dev/null; then
        cat > /tmp/councilkey.desktop << EOF
[Desktop Entry]
Name=CouncilKey-Os
Comment=3 AI Agents Portable Council
Exec=$USB_ROOT/start.sh
Icon=$USB_ROOT/start.sh
Terminal=false
Type=Application
Categories=Development;
EOF
        xdg-desktop-menu install --novendor /tmp/councilkey.desktop 2>/dev/null || true
        write_success "Desktop entry created"
    fi
    
    # macOS: create .command file for double-click
    if [[ "$OSTYPE" == "darwin"* ]]; then
        cat > "$USB_ROOT/Start CouncilKey-Os.command" << EOF
#!/bin/bash
cd "$(dirname "\$0")"
./start.sh
EOF
        chmod +x "$USB_ROOT/Start CouncilKey-Os.command"
        write_success "macOS launcher created"
    fi
    
    write_success "Launchers ready"
}

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --target) TARGET_PATH="$2"; shift 2 ;;
        --profile) PROFILE="$2"; shift 2 ;;
        --skip-build) SKIP_BUILD=true; shift ;;
        --no-auto-detect) AUTO_DETECT=false; shift ;;
        -h|--help) 
            echo "Usage: $0 [OPTIONS] [TARGET_PATH]"
            echo "Options:"
            echo "  --target PATH       Target USB path (e.g., /media/user/USB or /Volumes/USB)"
            echo "  --profile minimal|full  Install profile (default: full)"
            echo "  --skip-build        Skip build step (use existing build)"
            echo "  --no-auto-detect    Don't auto-detect USB"
            echo "  -h, --help          Show this help"
            exit 0
            ;;
        *) TARGET_PATH="$1"; shift ;;
    esac
done

# Determine target
if [[ -n "$TARGET_PATH" ]]; then
    USB_ROOT="$TARGET_PATH/CouncilKey-Os"
    AUTO_DETECT=false
elif [[ "$AUTO_DETECT" == "true" ]]; then
    detect_usb
else
    write_error "Specify target path or use --no-auto-detect with --target"
    exit 1
fi

echo -e "\nTarget: ${CYAN}$USB_ROOT${NC}"
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

trap 'write_error "Installation failed"; exit 1' ERR

check_prereqs
clone_repo
build_portable
deploy_usb
create_shortcuts

echo -e "\n${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ Installation Complete!              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}\n"

echo -e "USB Location: ${CYAN}$USB_ROOT${NC}"
echo -e "\nTo run CouncilKey-Os:"
echo -e "  1. Plug USB into any Windows/Linux/macOS machine"
echo -e "  2. Run: ${YELLOW}./start.sh${NC} (Linux/macOS) or ${YELLOW}start.bat${NC} (Windows)"
echo -e "  3. Open ${CYAN}http://localhost:8444${NC} in browser"
echo -e "\nFeatures:"
echo -e "  • 3 AI Agents (Hermes, OpenClaw, Agent Zero)"
echo -e "  • Works OFFLINE - zero internet required"
echo -e "  • Zero traces on host - all data on USB"
echo -e "  • Works on Windows, Linux, macOS"