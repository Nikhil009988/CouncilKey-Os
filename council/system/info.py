"""CouncilKey-Os system information collector."""
from __future__ import annotations

import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from council import __version__

_START_TIME = time.time()


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


def collect(council_home: str | None = None) -> dict[str, Any]:
    """Collect basic host/process/system facts."""
    home = Path(council_home or os.environ.get("COUNCIL_HOME", "/var/lib/council"))
    disk: dict[str, Any] = {}
    try:
        target = home if home.exists() else home.parent
        du = shutil.disk_usage(str(target))
        disk = {
            "total_bytes": du.total,
            "used_bytes": du.used,
            "free_bytes": du.free,
            "free_human": f"{du.free / 2**30:.1f}GB",
        }
    except Exception:
        pass

    uptime_s = int(time.time() - _START_TIME)
    return {
        "version": __version__,
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count() or 0,
        "uptime_seconds": uptime_s,
        "uptime_human": _human_uptime(uptime_s),
        "council_home": str(home),
        "disk": disk,
    }
