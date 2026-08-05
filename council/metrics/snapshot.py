"""CouncilKey-Os metrics helper - system + storage snapshot."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
_START_TIME = time.time()


def _human(n: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(n) < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


def snapshot(request_count: int = 0) -> dict[str, Any]:
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

    disk: dict[str, Any] = {}
    try:
        du = shutil.disk_usage(str(COUNCIL_HOME if COUNCIL_HOME.exists() else COUNCIL_HOME.parent))
        disk = {
            "total_bytes": du.total,
            "used_bytes": du.used,
            "free_bytes": du.free,
            "free_human": _human(du.free),
        }
    except Exception:
        pass

    from council.storage.optimizer import audit as storage_audit

    try:
        audit = storage_audit()
    except Exception:
        audit = {}

    uptime_s = int(time.time() - _START_TIME)

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cpu_percent": cpu,
        "memory_percent": mem,
        "storage_bytes": storage,
        "storage_human": _human(storage),
        "uptime_seconds": uptime_s,
        "uptime_human": _human_uptime(uptime_s),
        "request_count": request_count,
        "disk": disk,
        "storage_split": {
            "keep_human": audit.get("total_keep_human", "0B"),
            "cache_ram_human": audit.get("total_cache_ram_human", "0B"),
        },
    }


def _human_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)
