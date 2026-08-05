#!/usr/bin/env bash
# build-vendor-agents.sh - Vendor latest agent source code into repo for true portable

set -euo pipefail

# Get absolute path to repo root (where this script's grandparent is)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENDOR_DIR="$REPO_ROOT/tools/linux"

mkdir -p "$VENDOR_DIR"

echo "=== Vendoring Latest Agents ==="
echo "Repo: $REPO_ROOT"
echo "Vendor dir: $VENDOR_DIR"

# Function to clone with sparse checkout for Hermes
clone_hermes() {
    local dest="$VENDOR_DIR/hermes"
    echo "--- Hermes Agent ---"
    if [ -d "$dest/.git" ]; then
        echo "Updating Hermes..."
        cd "$dest"
        git fetch origin
        git checkout main
        git pull origin main
    else
        echo "Cloning Hermes (sparse)..."
        git clone --depth=1 --branch main --filter=blob:none --sparse https://github.com/NousResearch/hermes-agent.git "$dest"
        cd "$dest"
        git sparse-checkout set --no-cone '/*' '!plugins/platforms/irc'
    fi
}

clone_openclaw() {
    local dest="$VENDOR_DIR/openclaw"
    echo "--- OpenClaw ---"
    if [ -d "$dest/.git" ]; then
        echo "Updating OpenClaw..."
        cd "$dest"
        git fetch origin
        git checkout main
        git pull origin main
    else
        echo "Cloning OpenClaw (sparse)..."
        git clone --depth=1 --branch main --filter=blob:none --sparse https://github.com/openclaw/openclaw.git "$dest"
        cd "$dest"
        # Exclude problematic paths that don't work on exFAT/Windows
        git sparse-checkout set --no-cone \
            '/*' \
            '!extensions/feishu/skills/feishu-doc/references'
    fi
}

clone_agent_zero() {
    local dest="$VENDOR_DIR/agent-zero"
    echo "--- Agent Zero ---"
    if [ -d "$dest/.git" ]; then
        echo "Updating Agent Zero..."
        cd "$dest"
        git fetch origin
        git checkout main
        git pull origin main
    else
        echo "Cloning Agent Zero..."
        git clone --depth=1 --branch main https://github.com/agent0ai/agent-zero.git "$dest"
    fi
}

# Run cloning
clone_hermes
clone_openclaw
clone_agent_zero

# Verify
echo ""
echo "=== Verification ==="
for agent in hermes openclaw agent-zero; do
    if [ -d "$VENDOR_DIR/$agent" ]; then
        size=$(du -sh "$VENDOR_DIR/$agent" 2>/dev/null | cut -f1)
        echo "✅ $agent: $size"
    else
        echo "❌ $agent: MISSING"
    fi
done

# Create version manifest
cat > "$VENDOR_DIR/VERSIONS.md" <<EOF
# Vendored Agent Versions
Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

## Hermes Agent
- Repo: https://github.com/NousResearch/hermes-agent
- Commit: $(cd "$VENDOR_DIR/hermes" && git rev-parse HEAD 2>/dev/null || echo "unknown")
- Branch: $(cd "$VENDOR_DIR/hermes" && git branch --show-current 2>/dev/null || echo "unknown")

## OpenClaw
- Repo: https://github.com/openclaw/openclaw
- Commit: $(cd "$VENDOR_DIR/openclaw" && git rev-parse HEAD 2>/dev/null || echo "unknown")
- Branch: $(cd "$VENDOR_DIR/openclaw" && git branch --show-current 2>/dev/null || echo "unknown")

## Agent Zero
- Repo: https://github.com/agent0ai/agent-zero
- Commit: $(cd "$VENDOR_DIR/agent-zero" && git rev-parse HEAD 2>/dev/null || echo "unknown")
- Branch: $(cd "$VENDOR_DIR/agent-zero" && git branch --show-current 2>/dev/null || echo "unknown")
EOF

echo ""
echo "=== Done ==="
echo "Versions saved to $VENDOR_DIR/VERSIONS.md"