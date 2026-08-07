#!/usr/bin/env bash
# build-portable-env.sh - Create portable Python environment with all dependencies
# This creates a self-contained .venv that gets copied to USB

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENDOR_DIR="$REPO_ROOT/tools/linux"
USB_BUILD_DIR="$REPO_ROOT/build/portable"

mkdir -p "$USB_BUILD_DIR"

echo "=== Building Portable Environment ==="
echo "Repo: $REPO_ROOT"

# 1. Create base Python venv
echo ""
echo "--- Creating Python venv ---"
PYTHON_EXE="$(command -v python || command -v python3)"
if [ -z "$PYTHON_EXE" ]; then
    echo "ERROR: Python not found"
    exit 1
fi
echo "Using Python: $PYTHON_EXE"

# Convert paths to Windows format for Python on Windows
# In git-bash, /d/... maps to D:\...
WIN_USB_BUILD_DIR="$(cygpath -w "$USB_BUILD_DIR" 2>/dev/null || echo "$USB_BUILD_DIR" | sed 's|^/\([a-z]\)/|\U\1:/|')"
WIN_REPO_ROOT="$(cygpath -w "$REPO_ROOT" 2>/dev/null || echo "$REPO_ROOT" | sed 's|^/\([a-z]\)/|\U\1:/|')"
echo "Windows build dir: $WIN_USB_BUILD_DIR"
echo "Windows repo root: $WIN_REPO_ROOT"

# Remove any existing venv
rm -rf "$USB_BUILD_DIR/.venv"

echo "Creating venv at $WIN_USB_BUILD_DIR\\.venv..."
"$PYTHON_EXE" -m venv "$WIN_USB_BUILD_DIR\\.venv"

# Verify venv was created
if [ ! -d "$WIN_USB_BUILD_DIR\\.venv" ]; then
    echo "ERROR: venv directory not created at $WIN_USB_BUILD_DIR\\.venv"
    exit 1
fi

# Determine pip path (Windows)
PIP="$WIN_USB_BUILD_DIR\\.venv\\Scripts\\pip.exe"
PYTHON_VENV="$WIN_USB_BUILD_DIR\\.venv\\Scripts\\python.exe"

if [ ! -f "$PIP" ]; then
    echo "ERROR: pip not found at $PIP"
    echo "Venv contents:"
    ls -la "$WIN_USB_BUILD_DIR\\.venv\\"
    exit 1
fi

echo "Using pip: $PIP"
"$PYTHON_VENV" -m pip install --upgrade pip setuptools wheel

# 2. Install CouncilKey-Os in development mode
echo ""
echo "--- Installing CouncilKey-Os ---"
"$PYTHON_VENV" -m pip install -e "$WIN_REPO_ROOT[dev]"

# 3. Install agent dependencies
echo ""
echo "--- Installing Agent Dependencies ---"

# Hermes deps (from vendored source)
if [ -f "$VENDOR_DIR/hermes/pyproject.toml" ] || [ -f "$VENDOR_DIR/hermes/requirements.txt" ]; then
    echo "Installing Hermes deps..."
    WIN_HERMES="$(cygpath -w "$VENDOR_DIR/hermes" 2>/dev/null || echo "$VENDOR_DIR/hermes" | sed 's|^/\([a-z]\)/|\U\1:/|')"
    "$PYTHON_VENV" -m pip install -e "$WIN_HERMES" || true
fi

# Codex CLI (npm - local execution, no Docker)
if [ -d "$VENDOR_DIR/codex" ]; then
    echo "Installing Codex CLI..."
    npm install --prefix "$VENDOR_DIR/codex" --no-audit --no-fund @openai/codex || true
fi

# 4. Install common runtime deps
echo ""
echo "--- Installing Runtime Dependencies ---"
"$PYTHON_VENV" -m pip install \
    fastapi uvicorn httpx pydantic \
    lancedb pyarrow \
    psutil pyyaml \
    python-dotenv \
    edge-tts \
    openai-whisper \
    kokoro-onnx \
    elevenlabs \
    requests \
    websockets \
    || true

# 5. Copy portable Node.js (if available)
echo ""
echo "--- Node.js ---"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "Found Node.js $NODE_VERSION"
    # Could download portable Node.js here for Windows
else
    echo "Node.js not found - will need portable Node.js for Windows"
fi

# 6. Create startup scripts for portable
echo ""
echo "--- Creating Portable Startup ---"
cat > "$USB_BUILD_DIR/start.py" << 'PYEOF'
#!/usr/bin/env python3
"""CouncilKey-Os Portable Launcher."""
from __future__ import annotations
import os, sys, subprocess, argparse
from pathlib import Path

def get_usb_root() -> Path:
    return Path(__file__).parent.absolute()

def setup_env(usb_root: Path) -> dict:
    env = os.environ.copy()
    council_home = usb_root / "config" / "council"
    council_home.mkdir(parents=True, exist_ok=True)
    env["COUNCIL_HOME"] = str(council_home)
    temp_dir = usb_root / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(temp_dir)
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["XDG_CACHE_HOME"] = str(temp_dir)
    env["NPM_CONFIG_CACHE"] = str(temp_dir / "npm-cache")
    env["PIP_CACHE_DIR"] = str(temp_dir / "pip-cache")
    config_dir = usb_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    env["XDG_CONFIG_HOME"] = str(config_dir)
    env["XDG_DATA_HOME"] = str(config_dir / "data")
    env["HERMES_HOME"] = str(council_home / "hermes" / "real_home")
    env["OPENCLAW_HOME"] = str(council_home / "openclaw")
    env["CODEX_HOME"] = str(council_home / "codex")
    python_path = str(usb_root)
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = python_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = python_path
    return env

def run_dashboard(usb_root: Path, host: str, port: int, env: dict):
    venv_python = usb_root / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    if not venv_python.exists():
        print("ERROR: Virtual environment not found. Run build script first.")
        sys.exit(1)
    os.chdir(usb_root)
    cmd = [str(venv_python), "-m", "uvicorn", "council.orchestrator.main:app", "--host", host, "--port", str(port)]
    print(f"Starting CouncilKey-Os on http://{host}:{port}")
    print(f"COUNCIL_HOME: {env['COUNCIL_HOME']}")
    try:
        subprocess.run(cmd, env=env, check=True)
    except KeyboardInterrupt:
        print("\nShutting down...")

def main():
    parser = argparse.ArgumentParser(description="CouncilKey-Os Portable Launcher")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()
    usb_root = get_usb_root()
    env = setup_env(usb_root)
    run_dashboard(usb_root, args.host, args.port, env)

if __name__ == "__main__":
    main()
PYEOF

chmod +x "$USB_BUILD_DIR/start.py"

# 7. Create portable start.sh
cat > "$USB_BUILD_DIR/start.sh" << 'SHEOF'
#!/usr/bin/env bash
set -euo pipefail
USB_ROOT="$(cd "$(dirname "$0")" && pwd)"
COUNCIL_HOME="$USB_ROOT/config/council"
export TMPDIR="$USB_ROOT/temp"
export TEMP="$USB_ROOT/temp"
export TMP="$USB_ROOT/temp"
export XDG_CACHE_HOME="$USB_ROOT/temp"
export NPM_CONFIG_CACHE="$USB_ROOT/temp/npm-cache"
export PIP_CACHE_DIR="$USB_ROOT/temp/pip-cache"
export XDG_CONFIG_HOME="$USB_ROOT/config"
export XDG_DATA_HOME="$USB_ROOT/config/data"
export HERMES_HOME="$COUNCIL_HOME/hermes/real_home"
export OPENCLAW_HOME="$COUNCIL_HOME/openclaw"
export CODEX_HOME="$COUNCIL_HOME/codex"
mkdir -p "$COUNCIL_HOME"/{hermes/{keep,cache},openclaw/{keep,cache},codex/{keep,cache},shared,journal,secrets,council,lance}
mkdir -p "$USB_ROOT/temp"
if [ ! -d "$USB_ROOT/.venv" ]; then
    echo "ERROR: .venv not found. Run build script first."
    exit 1
fi
echo "Starting CouncilKey-Os on http://${COUNCIL_HOST:-0.0.0.0}:${COUNCIL_PORT:-8443}"
exec "$USB_ROOT/.venv/bin/python" -m uvicorn council.orchestrator.main:app --host "${COUNCIL_HOST:-0.0.0.0}" --port "${COUNCIL_PORT:-8443}"
SHEOF

chmod +x "$USB_BUILD_DIR/start.sh"

# 8. Create portable start.bat
cat > "$USB_BUILD_DIR/start.bat" << 'BATEOF'
@echo off
setlocal enabledelayedexpansion
set USB_ROOT=%~dp0
set USB_ROOT=!USB_ROOT:~0,-1!
set COUNCIL_HOME=%USB_ROOT%\config\council
set TMPDIR=%USB_ROOT%\temp
set TEMP=%USB_ROOT%\temp
set TMP=%USB_ROOT%\temp
set XDG_CACHE_HOME=%USB_ROOT%\temp
set NPM_CONFIG_CACHE=%USB_ROOT%\temp\npm-cache
set PIP_CACHE_DIR=%USB_ROOT%\temp\pip-cache
set XDG_CONFIG_HOME=%USB_ROOT%\config
set XDG_DATA_HOME=%USB_ROOT%\config\data
set HERMES_HOME=%COUNCIL_HOME%\hermes\real_home
set OPENCLAW_HOME=%COUNCIL_HOME%\openclaw
set CODEX_HOME=%COUNCIL_HOME%\codex
if not exist "%COUNCIL_HOME%" mkdir "%COUNCIL_HOME%"
if not exist "%COUNCIL_HOME%\hermes\keep" mkdir "%COUNCIL_HOME%\hermes\keep"
if not exist "%COUNCIL_HOME%\hermes\cache" mkdir "%COUNCIL_HOME%\hermes\cache"
if not exist "%COUNCIL_HOME%\openclaw\keep" mkdir "%COUNCIL_HOME%\openclaw\keep"
if not exist "%COUNCIL_HOME%\openclaw\cache" mkdir "%COUNCIL_HOME%\openclaw\cache"
if not exist "%COUNCIL_HOME%\codex\keep" mkdir "%COUNCIL_HOME%\codex\keep"
if not exist "%COUNCIL_HOME%\codex\cache" mkdir "%COUNCIL_HOME%\codex\cache"
if not exist "%COUNCIL_HOME%\shared" mkdir "%COUNCIL_HOME%\shared"
if not exist "%COUNCIL_HOME%\journal" mkdir "%COUNCIL_HOME%\journal"
if not exist "%COUNCIL_HOME%\secrets" mkdir "%COUNCIL_HOME%\secrets"
if not exist "%COUNCIL_HOME%\council" mkdir "%COUNCIL_HOME%\council"
if not exist "%COUNCIL_HOME%\lance" mkdir "%COUNCIL_HOME%\lance"
if not exist "%USB_ROOT%\temp" mkdir "%USB_ROOT%\temp"
if not exist "%USB_ROOT%\.venv" (
    echo ERROR: .venv not found. Run build script first.
    exit /b 1
)
echo Starting CouncilKey-Os on http://%COUNCIL_HOST%:%COUNCIL_PORT%
"%USB_ROOT%\.venv\Scripts\python.exe" -m uvicorn council.orchestrator.main:app --host %COUNCIL_HOST% --port %COUNCIL_PORT%
BATEOF

echo ""
echo "=== Portable build complete ==="
echo "Output: $USB_BUILD_DIR"
echo "Contents:"
ls -la "$USB_BUILD_DIR"