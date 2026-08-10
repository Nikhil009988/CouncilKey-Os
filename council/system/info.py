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


def _cpu_percent() -> float | None:
    """Live CPU usage: psutil when available, /proc fallback on Linux."""
    try:
        import psutil

        return round(psutil.cpu_percent(interval=0.2), 1)
    except Exception:
        pass
    try:  # Linux /proc fallback (no psutil)
        with open("/proc/stat", encoding="utf-8") as fh:
            vals = [int(v) for v in fh.readline().split()[1:]]
        total = sum(vals)
        idle = vals[3]
        now = (total, idle)
        last = getattr(_cpu_percent, "_last", None)
        _cpu_percent._last = now  # type: ignore[attr-defined]
        if last and now[0] > last[0]:
            delta_total = now[0] - last[0]
            delta_idle = now[1] - last[1]
            return round(100.0 * (1 - delta_idle / delta_total), 1)
        return 0.0
    except Exception:
        return None


def _ram() -> dict[str, Any]:
    """Live RAM: psutil when available, /proc/meminfo fallback on Linux."""
    try:
        import psutil

        vm = psutil.virtual_memory()
        return {
            "total_bytes": vm.total,
            "used_bytes": vm.used,
            "percent": round(vm.percent, 1),
            "used_human": f"{vm.used / 2**30:.1f}GB / {vm.total / 2**30:.1f}GB",
        }
    except Exception:
        pass
    try:  # Linux /proc/meminfo fallback
        mem = {}
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split(":")
                if parts and parts[0] in ("MemTotal", "MemAvailable"):
                    kb = int(parts[1].strip().split()[0])
                    mem[parts[0]] = kb * 1024
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        used = max(total - avail, 0)
        if total:
            return {
                "total_bytes": total,
                "used_bytes": used,
                "percent": round(100.0 * used / total, 1),
                "used_human": f"{used / 2**30:.1f}GB / {total / 2**30:.1f}GB",
            }
    except Exception:
        pass
    return {}


def collect(council_home: str | None = None) -> dict[str, Any]:
    """Collect basic host/process/system facts + live CPU/RAM."""
    home = Path(council_home or os.environ.get("COUNCIL_HOME", "/var/lib/council"))
    disk: dict[str, Any] = {}
    try:
        target = home if home.exists() else home.parent
        du = shutil.disk_usage(str(target))
        disk = {
            "total_bytes": du.total,
            "used_bytes": du.used,
            "free_bytes": du.free,
            "used_percent": round(100.0 * du.used / du.total, 1) if du.total else 0.0,
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
        "cpu_percent": _cpu_percent(),
        "ram": _ram(),
        "uptime_seconds": uptime_s,
        "uptime_human": _human_uptime(uptime_s),
        "council_home": str(home),
        "disk": disk,
    }
