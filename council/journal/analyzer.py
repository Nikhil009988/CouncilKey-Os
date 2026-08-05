"""CouncilKey-Os journal analyzer."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

JOURNAL_DIR = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")) / "journal"


def list_journal() -> dict[str, object]:
    if not JOURNAL_DIR.exists():
        return {"journal_dir": str(JOURNAL_DIR), "files": []}
    files = []
    for p in sorted(JOURNAL_DIR.glob("*.md")):
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            content = ""
        files.append({"file": p.name, "size": p.stat().st_size, "content": content})
    return {"journal_dir": str(JOURNAL_DIR), "files": files[-50:]}


def analyze() -> dict[str, object]:
    data = list_journal()
    total = len(data["files"])
    best_agents: dict[str, int] = {}
    strategies: dict[str, int] = {}
    for item in data["files"]:
        text = str(item.get("content", "")) if isinstance(item, dict) else ""
        m = re.search(r"best_agent\": \"([^\"]+)\"", text)
        if m:
            best_agents[m.group(1)] = best_agents.get(m.group(1), 0) + 1
        m = re.search(r"## Strategy\n([^\n]+)", text)
        if m:
            strategies[m.group(1)] = strategies.get(m.group(1), 0) + 1
    return {"total_entries": total, "best_agents": best_agents, "strategies": strategies}
