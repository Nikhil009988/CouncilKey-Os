"""CouncilKey-Os Backup manager."""
from __future__ import annotations

import os
import tarfile
import time
from pathlib import Path

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))


def create_backup() -> dict[str, Any]:
    backups = COUNCIL_HOME / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    out = backups / f"council-{time.strftime('%Y-%m-%d')}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        for rel in ["hermes/keep", "openclaw/keep", "agent-zero/keep", "shared", "journal", "council"]:
            p = COUNCIL_HOME / rel
            if p.exists():
                tar.add(p, arcname=rel)
    return {"ok": True, "path": str(out)}


def list_backups() -> dict[str, Any]:
    backups = COUNCIL_HOME / "backups"
    if not backups.exists():
        return {"backups": []}
    return {"backups": [p.name for p in sorted(backups.glob("*.tar.gz"))]}
