"""CouncilKey-Os Memory Consolidation."""
from __future__ import annotations

import os
import time
from pathlib import Path

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))


def nightly_consolidate() -> dict[str, Any]:
    hermes_mem = COUNCIL_HOME / "hermes" / "keep" / "MEMORY.md"
    actions = []
    if hermes_mem.exists():
        content = hermes_mem.read_text(encoding="utf-8", errors="ignore")
        if len(content) > 20000:
            backup = hermes_mem.with_suffix(".md.bak")
            backup.write_text(content, encoding="utf-8")
            hermes_mem.write_text(content[:20000] + "\n\n> Auto-compacted by nightly consolidation.\n", encoding="utf-8")
            actions.append(f"compacted {hermes_mem}")
    return {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "actions": actions}
