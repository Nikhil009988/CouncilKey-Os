"""CouncilKey-Os backup manager - create, list, restore."""
from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))

# Top-level directories that may be backed up / restored.
BACKUP_RELS = ["hermes/keep", "openclaw/keep", "opencode/keep", "shared", "journal", "council", "secrets"]
ALLOWED_TOP = {rel.split("/")[0] for rel in BACKUP_RELS}


def create_backup() -> dict[str, Any]:
    backups = COUNCIL_HOME / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    out = backups / f"council-{time.strftime('%Y-%m-%d')}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        for rel in BACKUP_RELS:
            p = COUNCIL_HOME / rel
            if p.exists():
                tar.add(p, arcname=rel)
    return {"ok": True, "path": str(out), "size": out.stat().st_size}


def list_backups() -> dict[str, Any]:
    backups = COUNCIL_HOME / "backups"
    if not backups.exists():
        return {"backups": []}
    return {"backups": sorted(p.name for p in backups.glob("*.tar.gz"))}


def restore_backup(name: str) -> dict[str, Any]:
    """Restore a backup archive, merging only known top-level dirs back in."""
    if not name.endswith(".tar.gz") or "/" in name or "\\" in name or name in (".", ".."):
        return {"ok": False, "error": "invalid backup name"}
    backups = COUNCIL_HOME / "backups"
    target = backups / name
    if not target.exists():
        return {"ok": False, "error": f"backup {name!r} not found"}

    try:
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(target, "r:gz") as tar:
                members = [m for m in tar.getmembers() if m.name.split("/")[0] in ALLOWED_TOP]
                tar.extractall(tmp, members=members)
            tmpdir = Path(tmp)
            restored = []
            for rel in sorted(ALLOWED_TOP):
                src = tmpdir / rel
                if not src.exists():
                    continue
                dst = COUNCIL_HOME / rel
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                restored.append(rel)
        return {"ok": True, "restored": restored, "backup": name}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
