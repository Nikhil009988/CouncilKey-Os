"""CouncilKey-Os storage optimizer."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))


def _size(p: Path) -> int:
    try:
        return p.stat().st_size
    except Exception:
        return 0


def _human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(n) < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


def _walk_keep_cache() -> dict[str, Any]:
    keep_dirs = {
        "hermes": COUNCIL_HOME / "hermes" / "keep",
        "openclaw": COUNCIL_HOME / "openclaw" / "keep",
        "agent-zero": COUNCIL_HOME / "agent-zero" / "keep",
        "shared": COUNCIL_HOME / "shared",
        "journal": COUNCIL_HOME / "journal",
        "council": COUNCIL_HOME / "council",
        "secrets": COUNCIL_HOME / "secrets",
    }
    cache_dirs = {
        "hermes": COUNCIL_HOME / "hermes" / "cache",
        "openclaw": COUNCIL_HOME / "openclaw" / "cache",
        "agent-zero": COUNCIL_HOME / "agent-zero" / "cache",
    }
    agents: dict[str, Any] = {}
    for name, root in keep_dirs.items():
        size = sum(_size(p) for p in root.rglob("*") if p.is_file()) if root.exists() else 0
        agents[name] = {"keep_size": size, "keep_size_human": _human(size), "keep_files": 0}
        try:
            agents[name]["keep_files"] = sum(1 for _ in root.rglob("*") if _.is_file()) if root.exists() else 0
        except Exception:
            pass
    total_cache = 0
    cache_files = []
    for name, root in cache_dirs.items():
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file():
                sz = _size(p)
                total_cache += sz
                cache_files.append(
                    {
                        "path": str(p),
                        "size": sz,
                        "human": _human(sz),
                        "reason": f"{name} cache - auto delete on unplug",
                        "agent": name,
                        "type": "cache_ram",
                    }
                )
    return {
        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "council_home": str(COUNCIL_HOME),
        "agents": agents,
        "total_keep": sum(v["keep_size"] for v in agents.values()),
        "total_keep_human": _human(sum(v["keep_size"] for v in agents.values())),
        "total_cache_ram": total_cache,
        "total_cache_ram_human": _human(total_cache),
        "total_cache_persist_leaked": 0,
        "total_cache_persist_leaked_human": "0B",
    }


def audit() -> dict[str, Any]:
    return _walk_keep_cache()


def what_if_delete() -> dict[str, Any]:
    cache_dirs = {
        "hermes": COUNCIL_HOME / "hermes" / "cache",
        "openclaw": COUNCIL_HOME / "openclaw" / "cache",
        "agent-zero": COUNCIL_HOME / "agent-zero" / "cache",
    }
    files = []
    total = 0
    for agent, root in cache_dirs.items():
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file():
                sz = _size(p)
                total += sz
                files.append(
                    {
                        "path": str(p),
                        "size": sz,
                        "human": _human(sz),
                        "reason": f"{agent} cache - safe to delete",
                        "agent": agent,
                        "type": "cache_ram",
                    }
                )
    return {
        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "files": files[:500],
        "total_files": len(files),
        "total_size": total,
        "total_size_human": _human(total),
        "message": "RAW heavy data -> DELETE. Distilled -> KEEP.",
    }


def optimize(dry_run: bool = False) -> dict[str, Any]:
    actions: list[str] = []
    saved = 0
    journal = COUNCIL_HOME / "journal"
    if journal.exists():
        for p in journal.glob("*.md.gz"):
            if not dry_run:
                p.unlink()
            actions.append(f"Removed compressed journal {p.name}")
            saved += _size(p)
    return {
        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "actions": actions[:50],
        "saved_bytes": saved,
        "saved_human": _human(saved),
        "dry_run": dry_run,
    }


def setup_persist_structure() -> dict[str, Any]:
    dirs = [
        COUNCIL_HOME / "secrets",
        COUNCIL_HOME / "hermes" / "keep",
        COUNCIL_HOME / "hermes" / "cache",
        COUNCIL_HOME / "openclaw" / "keep",
        COUNCIL_HOME / "openclaw" / "cache",
        COUNCIL_HOME / "agent-zero" / "keep",
        COUNCIL_HOME / "agent-zero" / "cache",
        COUNCIL_HOME / "shared",
        COUNCIL_HOME / "journal",
        COUNCIL_HOME / "council",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "home": str(COUNCIL_HOME)}
