#!/usr/bin/env python3
"""Add OPENCLAW_WORKSPACE_DIR + OPENCLAW_HOME to the pendrive OpenClaw launchers."""
from pathlib import Path

# ---- fix the .sh template inside pendrive-setup.sh ----
p = Path("scripts/pendrive-setup.sh")
s = p.read_text(encoding="utf-8")
orig = s

old_sh = '''cat > "$USB/run-openclaw.sh" <<'EOF'
#!/usr/bin/env bash
# run-openclaw.sh - OpenClaw from the pendrive (Linux/macOS)
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
export OPENCLAW_STATE_DIR="$STICK/council-data/openclaw"
export OPENCLAW_CONFIG_PATH="$STICK/council-data/openclaw/openclaw.json"
if [ -x "$STICK/CouncilKey-Os/tools/openclaw/node_modules/.bin/openclaw" ]; then
  exec "$STICK/CouncilKey-Os/tools/openclaw/node_modules/.bin/openclaw" "$@"
else
  exec openclaw "$@"
fi
EOF'''
new_sh = '''cat > "$USB/run-openclaw.sh" <<'EOF'
#!/usr/bin/env bash
# run-openclaw.sh - OpenClaw from the pendrive (Linux/macOS)
# Every path OpenClaw uses (state, config, workspace, home) is on the stick.
set -euo pipefail
STICK="$(cd "$(dirname "$0")" && pwd)"
export OPENCLAW_STATE_DIR="$STICK/council-data/openclaw"
export OPENCLAW_CONFIG_PATH="$STICK/council-data/openclaw/openclaw.json"
export OPENCLAW_WORKSPACE_DIR="$STICK/council-data/openclaw/workspace"
export OPENCLAW_HOME="$STICK/council-data/openclaw/home"
mkdir -p "$OPENCLAW_WORKSPACE_DIR" "$OPENCLAW_HOME"
if [ -x "$STICK/CouncilKey-Os/tools/openclaw/node_modules/.bin/openclaw" ]; then
  exec "$STICK/CouncilKey-Os/tools/openclaw/node_modules/.bin/openclaw" "$@"
else
  exec openclaw "$@"
fi
EOF'''
assert old_sh in s, "run-openclaw.sh template"
s = s.replace(old_sh, new_sh)

old_bat = '''set "OPENCLAW_STATE_DIR=%STICK%council-data\\openclaw"
set "OPENCLAW_CONFIG_PATH=%STICK%council-data\\openclaw\\openclaw.json"'''
new_bat = '''set "OPENCLAW_STATE_DIR=%STICK%council-data\\openclaw"
set "OPENCLAW_CONFIG_PATH=%STICK%council-data\\openclaw\\openclaw.json"
set "OPENCLAW_WORKSPACE_DIR=%STICK%council-data\\openclaw\\workspace"
set "OPENCLAW_HOME=%STICK%council-data\\openclaw\\home"
if not exist "%STICK%council-data\\openclaw\\workspace" mkdir "%STICK%council-data\\openclaw\\workspace"'''
assert old_bat in s, "RUN-OPENCLAW.bat template"
s = s.replace(old_bat, new_bat)
p.write_text(s, encoding="utf-8")
print("pendrive-setup.sh launchers fixed" if s != orig else "NO CHANGE (sh)")

# ---- fix the .ps1 ----
p2 = Path("scripts/pendrive-setup.ps1")
s2 = p2.read_text(encoding="utf-8")
orig2 = s2
old_ps = '''set "OPENCLAW_STATE_DIR=%STICK%council-data\\openclaw"
set "OPENCLAW_CONFIG_PATH=%STICK%council-data\\openclaw\\openclaw.json"'''
new_ps = '''set "OPENCLAW_STATE_DIR=%STICK%council-data\\openclaw"
set "OPENCLAW_CONFIG_PATH=%STICK%council-data\\openclaw\\openclaw.json"
set "OPENCLAW_WORKSPACE_DIR=%STICK%council-data\\openclaw\\workspace"
set "OPENCLAW_HOME=%STICK%council-data\\openclaw\\home"
if not exist "%STICK%council-data\\openclaw\\workspace" mkdir "%STICK%council-data\\openclaw\\workspace"'''
assert old_ps in s2, "ps1 launcher"
s2 = s2.replace(old_ps, new_ps)
p2.write_text(s2, encoding="utf-8")
print("pendrive-setup.ps1 launcher fixed" if s2 != orig2 else "NO CHANGE (ps1)")
