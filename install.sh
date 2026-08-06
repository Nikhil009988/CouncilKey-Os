#!/usr/bin/env bash
# install.sh - One-line installer for CouncilKey-Os.
#
#   curl -fsSL https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/install.sh | bash
#
# Clones the repo (into ~/councilkey-os by default) and runs the full setup:
# Python env + the interactive wizard (model provider + API key) + optional
# external agents.
# Flags: --no-agents, --skip-tests
set -euo pipefail

DEST="${1:-$HOME/councilkey-os}"

echo "== CouncilKey-Os installer =="
echo "Installing to: $DEST"

if [ -d "$DEST/.git" ]; then
  echo "Repo already present - updating..."
  git -C "$DEST" pull --ff-only
else
  git clone --depth 1 https://github.com/Nikhil009988/CouncilKey-Os.git "$DEST"
fi

exec "$DEST/scripts/setup.sh" "${@:2}"
