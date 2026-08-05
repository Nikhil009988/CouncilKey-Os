"""CouncilKey-Os metrics helper."""
from __future__ import annotations

import os
import time
from pathlib import Path

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))


def snapshot() -> dict[str, object]:
    try:
        import psutil  # type: ignore
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu = 0.0
        mem = 0.0
    storage = 0
    if COUNCIL_HOME.exists():
        for p in COUNCIL_HOME.rglob("*"):
            if p.is_file():
                try:
                    storage += p.stat().st_size
                except Exception:
                    pass
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cpu_percent": cpu,
        "memory_percent": mem,
        "storage_bytes": storage,
        "storage_human": _human(storage),
    }


def _human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(n) < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"
