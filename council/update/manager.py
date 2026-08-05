"""CouncilKey-Os update manager."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


def current_version() -> str:
    try:
        return Path("VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "1.0.0-dev"


def check_update(repo: str = "nikhilgundu99/CouncilKey-Os") -> dict[str, object]:
    if httpx is None:
        return {"update_available": False, "error": "httpx not installed"}
    try:
        r = httpx.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=10)
        if r.status_code != 200:
            return {"update_available": False, "status": r.status_code}
        data = r.json()
        latest = data.get("tag_name", current_version())
        return {"update_available": latest != current_version(), "latest": latest, "current": current_version()}
    except Exception as exc:
        return {"update_available": False, "error": str(exc)} 
