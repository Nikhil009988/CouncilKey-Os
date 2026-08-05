#!/usr/bin/env bash
set -euo pipefail
COUNCIL_HOME="${COUNCIL_HOME:-/var/lib/council}"
python -m council.orchestrator.main
