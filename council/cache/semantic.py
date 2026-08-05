"""Semantic result cache for council asks (JSONL, TTL + size cap)."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

CACHE_FILE = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")) / "cache" / "council-cache.jsonl"
_lock = threading.Lock()


def _lines() -> list[str]:
    if not CACHE_FILE.exists():
        return []
    try:
        return CACHE_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []


def _write(lines: list[str]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def get(key: str, ttl: float = 3600) -> Any | None:
    """Return cached result for key if fresh, else None."""
    now = time.time()
    with _lock:
        for line in reversed(_lines()[-2000:]):
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("k") != key:
                continue
            if now - entry.get("t", 0) <= ttl:
                return entry.get("result")
            return None
    return None


def put(key: str, result: Any, max_entries: int = 500) -> None:
    """Store a result under key, capping the number of cached entries."""
    with _lock:
        lines = [ln for ln in _lines() if ln and key not in ln]
        lines = lines[-(max_entries - 1):]
        lines.append(json.dumps({"k": key, "t": time.time(), "result": result}, ensure_ascii=False, default=str))
        _write(lines)


def stats() -> dict:
    with _lock:
        lines = _lines()
    entries = 0
    expired = 0
    for ln in lines:
        try:
            entry = json.loads(ln)
            if time.time() - entry.get("t", 0) > 3600:
                expired += 1
            entries += 1
        except Exception:
            pass
    return {"entries": entries, "expired": expired, "file": str(CACHE_FILE)}


def flush() -> dict:
    with _lock:
        _write([])
    return {"ok": True}
