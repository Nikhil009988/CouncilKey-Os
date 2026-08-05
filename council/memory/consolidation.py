"""CouncilKey-Os Memory Consolidation + summary."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))

# Keep memory below this size; older content is compacted to a .bak file.
MAX_MEMORY_CHARS = 20_000


def nightly_consolidate() -> dict[str, Any]:
    hermes_mem = COUNCIL_HOME / "hermes" / "keep" / "MEMORY.md"
    actions = []
    if hermes_mem.exists():
        content = hermes_mem.read_text(encoding="utf-8", errors="ignore")
        if len(content) > MAX_MEMORY_CHARS:
            backup = hermes_mem.with_suffix(".md.bak")
            backup.write_text(content, encoding="utf-8")
            hermes_mem.write_text(
                content[:MAX_MEMORY_CHARS] + "\n\n> Auto-compacted by nightly consolidation.\n",
                encoding="utf-8",
            )
            actions.append(f"compacted {hermes_mem.name} ({len(content)} -> {MAX_MEMORY_CHARS} chars)")
    return {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "actions": actions}


def memory_summary() -> dict[str, Any]:
    """Preview of Hermes long-term memory."""
    hermes_mem = COUNCIL_HOME / "hermes" / "keep" / "MEMORY.md"
    if not hermes_mem.exists():
        return {"exists": False, "path": str(hermes_mem), "chars": 0, "preview": ""}
    content = hermes_mem.read_text(encoding="utf-8", errors="ignore")
    return {
        "exists": True,
        "path": str(hermes_mem),
        "chars": len(content),
        "lines": len(content.splitlines()),
        "preview": content[:500],
    }
