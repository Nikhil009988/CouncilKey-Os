#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USB="${1:-}"
if [ -z "$USB" ]; then echo "Usage: $0 /mnt/usb"; exit 1; fi
mkdir -p "$USB"/{bin/linux,config/council,tools/linux,scripts}
if [ ! -f "$USB/bin/linux/node-v22.14-linux-x64.tar.xz" ]; then
  echo "Place portable Node.js tarball at $USB/bin/linux/node-v22.14-linux-x64.tar.xz"
fi
if [ ! -d "$USB/tools/linux/hermes" ]; then
  git clone --depth=1 https://github.com/NousResearch/hermes-agent.git "$USB/tools/linux/hermes" || true
fi
if [ ! -d "$USB/tools/linux/agent-zero" ]; then
  git clone --depth=1 https://github.com/frdel/agent-zero-exe.git "$USB/tools/linux/agent-zero" || true
fi
cp "$ROOT/council/orchestrator/main.py" "$USB/tools/linux/council-core/main.py"
cp "$ROOT/scripts/start.sh" "$USB/start.sh"
chmod +x "$USB/start.sh"
echo "Portable council built at $USB"
