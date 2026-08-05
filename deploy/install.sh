#!/usr/bin/env bash
# install.sh - Install CouncilKey-Os as a systemd service.
# Requires root (sudo). Installs to /opt/councilkey and enables the service.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST=/opt/councilkey

echo "=== Installing CouncilKey-Os systemd service ==="

sudo mkdir -p "$DEST"
sudo cp -r "$ROOT/council" "$ROOT/VERSION" "$ROOT/pyproject.toml" "$ROOT/README.md" "$DEST/"
sudo cp -r "$ROOT/scripts" "$DEST/scripts"

if [ ! -d "$DEST/.venv" ]; then
  echo "--- Creating venv ---"
  sudo python3 -m venv "$DEST/.venv"
  sudo "$DEST/.venv/bin/pip" install -q -e "$DEST"
fi

sudo mkdir -p /var/lib/council/{secrets,shared,journal,council,backups}
sudo mkdir -p /var/lib/council/{hermes,openclaw,agent-zero}/{keep,cache}
sudo useradd -r -d /var/lib/council -s /usr/sbin/nologin council 2>/dev/null || true
sudo chown -R council:council /var/lib/council

sudo cp "$ROOT/deploy/councilkey.service" /etc/systemd/system/councilkey.service
sudo systemctl daemon-reload
sudo systemctl enable councilkey
sudo systemctl start councilkey

echo "✅ CouncilKey-Os installed - status:"
systemctl --no-pager status councilkey | head -8
