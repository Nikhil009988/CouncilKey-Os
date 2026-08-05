"""CouncilKey-Os Self-Reflection."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))


def reflect_on_last() -> dict[str, Any]:
    journal = COUNCIL_HOME / "journal"
    files = sorted(journal.glob("*.md")) if journal.exists() else []
    last = files[-1] if files else None
    if not last:
        return {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "reflection": "No journal entries yet."}
    text = last.read_text(encoding="utf-8", errors="ignore")
    reflection = f"Reflected on {last.name}: {len(text)} chars."
    return {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "file": last.name, "reflection": reflection}
