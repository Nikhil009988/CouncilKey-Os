"""CouncilKey-Os Tailscale network helper."""
from __future__ import annotations

import subprocess
from typing import Any


def tailscale_status() -> dict[str, Any]:
    try:
        out = subprocess.check_output(["tailscale", "status", "--json"], text=True)
        return {"installed": True, "running": True, "raw": out}
    except FileNotFoundError:
        return {"installed": False, "running": False}
    except subprocess.CalledProcessError as exc:
        return {"installed": True, "running": False, "error": str(exc)}


def setup_tailscale(auth_key: str | None = None) -> dict[str, Any]:
    if not auth_key:
        return {"ok": False, "error": "auth_key required"}
    try:
        subprocess.run(["tailscale", "up", "--authkey", auth_key], check=True)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
