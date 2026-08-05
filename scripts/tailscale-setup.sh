#!/usr/bin/env bash
# tailscale-setup.sh - Bring up Tailscale networking for CouncilKey-Os.
#
# Usage:
#   ./scripts/tailscale-setup.sh <AUTH_KEY>   # up with auth key (or TS_AUTHKEY env)
#   ACTION=down  ./scripts/tailscale-setup.sh # take tailscale down
#   ACTION=status ./scripts/tailscale-setup.sh# show status
set -euo pipefail

AUTH_KEY="${1:-${TS_AUTHKEY:-}}"
ACTION="${ACTION:-up}"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "❌ tailscale not installed. Install with: curl -fsSL https://tailscale.com/install.sh | sh" >&2
  exit 1
fi

case "$ACTION" in
  down)
    tailscale down
    echo "✅ tailscale down"
    exit 0
    ;;
  status)
    if tailscale status >/dev/null 2>&1; then
      tailscale status
    else
      echo "tailscale is installed but not up"
      exit 1
    fi
    exit 0
    ;;
  up) ;;
  *)
    echo "❌ unknown ACTION '$ACTION' (use up|down|status)" >&2
    exit 1
    ;;
esac

if tailscale status >/dev/null 2>&1; then
  echo "✅ tailscale already up"
  tailscale status
  exit 0
fi

if [ -z "$AUTH_KEY" ]; then
  echo "❌ auth key required - pass as first argument or set TS_AUTHKEY env" >&2
  exit 1
fi

tailscale up --authkey "$AUTH_KEY" --ssh --accept-routes
echo "✅ tailscale up"
tailscale ip -4 || true
