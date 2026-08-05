"""CouncilKey-Os Canvas - sandboxed file browser + live document editing.

Real implementation: browse / read / write files inside COUNCIL_HOME,
with strict path confinement (no traversal outside the council home).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")).resolve()
MAX_READ_CHARS = 200_000
MAX_WRITE_CHARS = 1_000_000


def _resolve(rel: str) -> Path | None:
    """Resolve a user-supplied relative path, rejecting traversal outside ROOT."""
    rel = (rel or "").strip()
    if not rel:
        return ROOT
    p = (ROOT / rel.lstrip("/\\")).resolve()
    try:
        common = os.path.commonpath([str(ROOT), str(p)])
    except ValueError:
        return None
    if common != str(ROOT):
        return None
    return p


def list_dir(rel: str = "") -> dict[str, Any]:
    p = _resolve(rel)
    if p is None:
        return {"ok": False, "error": "path outside council home"}
    if not p.exists():
        return {"ok": False, "error": f"path not found: {rel or '/'}"}
    if not p.is_dir():
        return {"ok": False, "error": f"not a directory: {rel or '/'}"}
    entries = []
    for child in sorted(p.iterdir(), key=lambda c: (c.is_file(), c.name.lower())):
        try:
            stat = child.stat()
        except OSError:
            continue
        entries.append(
            {
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": stat.st_size,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            }
        )
    return {"ok": True, "path": str(p), "rel": str(p.relative_to(ROOT)) if p != ROOT else "", "entries": entries}


def read_file(rel: str) -> dict[str, Any]:
    p = _resolve(rel)
    if p is None:
        return {"ok": False, "error": "path outside council home"}
    if not p.exists() or not p.is_file():
        return {"ok": False, "error": f"file not found: {rel}"}
    try:
        raw = p.read_bytes()[: MAX_READ_CHARS * 4]
        text = raw.decode("utf-8", errors="replace")
        return {
            "ok": True,
            "path": str(p),
            "size": p.stat().st_size,
            "truncated": len(text) > MAX_READ_CHARS,
            "content": text[:MAX_READ_CHARS],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def write_file(rel: str, content: str) -> dict[str, Any]:
    p = _resolve(rel)
    if p is None:
        return {"ok": False, "error": "path outside council home"}
    if len(content) > MAX_WRITE_CHARS:
        return {"ok": False, "error": f"content too large (max {MAX_WRITE_CHARS} chars)"}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes": p.stat().st_size}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def make_dir(rel: str) -> dict[str, Any]:
    p = _resolve(rel)
    if p is None:
        return {"ok": False, "error": "path outside council home"}
    try:
        p.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "path": str(p)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def canvas_tools() -> list[dict[str, str]]:
    """Tool descriptors for UI/agent documentation."""
    return [
        {"name": "canvas_file_browser", "description": "Explore and preview files inside council home - implemented"},
        {"name": "canvas_read_write", "description": "Read and edit live documents (Markdown, notes, configs) - implemented"},
        {"name": "canvas_full_desktop", "description": "Full Linux desktop via noVNC (optional, requires host setup)"},
        {"name": "canvas_multi_agent_cooperation", "description": "Delegate research/coding/analysis tasks to subagents"},
    ]


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        print(json.dumps(list_dir(sys.argv[1]), indent=2))
    else:
        print(json.dumps(list_dir(), indent=2))
