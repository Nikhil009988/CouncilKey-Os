"""CouncilKey-Os journal analyzer + chat history."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

JOURNAL_DIR = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")) / "journal"


def list_journal() -> dict[str, Any]:
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


def analyze() -> dict[str, Any]:
    data = list_journal()
    total = len(data["files"])
    best_agents: dict[str, int] = {}
    strategies: dict[str, int] = {}
    consensus_yes = 0
    consensus_no = 0
    for item in data["files"]:
        text = str(item.get("content", "")) if isinstance(item, dict) else ""
        m = re.search(r"best_agent\": \"([^\"]+)\"", text)
        if m:
            best_agents[m.group(1)] = best_agents.get(m.group(1), 0) + 1
        m = re.search(r"## Strategy\n([^\n]+)", text)
        if m:
            strategies[m.group(1)] = strategies.get(m.group(1), 0) + 1
        if "Consensus" in text:
            if "✅" in text:
                consensus_yes += 1
            elif "❌" in text:
                consensus_no += 1
    return {
        "total_entries": total,
        "best_agents": best_agents,
        "strategies": strategies,
        "consensus_reached": consensus_yes,
        "consensus_missed": consensus_no,
    }


def history(limit: int = 20) -> list[dict[str, Any]]:
    """Parse journal entries into a compact chat-history shape."""
    if not JOURNAL_DIR.exists():
        return []
    entries: list[dict[str, Any]] = []
    for p in sorted(JOURNAL_DIR.glob("*.md"))[-limit:]:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = text.splitlines()
        prompt = ""
        final_lines: list[str] = []
        in_final = False
        for i, line in enumerate(lines):
            if line.startswith("## Prompt") and i + 1 < len(lines):
                prompt = lines[i + 1].strip()
            elif line.startswith("## Final"):
                in_final = True
                continue
            elif in_final and line.startswith("## "):
                break
            elif in_final:
                final_lines.append(line)
        entries.append(
            {
                "file": p.name,
                "timestamp": p.stem.split("-", 2)[:2],  # [date, time]
                "prompt": prompt[:300],
                "final": " ".join(final_lines)[:500],
                "size": p.stat().st_size,
            }
        )
    return entries
