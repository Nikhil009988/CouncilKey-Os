#!/usr/bin/env bash
# install.sh - One-line installer for CouncilKey-Os.
#
#   curl -fsSL https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/arena/019fd1ec-councilkey-os/install.sh | bash
#
# Clones the repo (into ~/councilkey-os by default) and runs the full setup:
# Python env + local LLM (Ollama, makes the council answer) + optional
# external agents via their official installers.
# Flags: --no-agents, --no-llm, --skip-tests
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
