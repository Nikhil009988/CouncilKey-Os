"""CouncilKey-Os Skill Evolution + skill listing."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))

_BUILTIN_SKILLS = [
    "council-reflection",
    "storage-health",
    "consensus-vote",
    "prompt-hygiene",
    "backup-discipline",
]


def evolve() -> dict[str, Any]:
    skills_dir = COUNCIL_HOME / "shared" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for name in _BUILTIN_SKILLS:
        p = skills_dir / f"{name}.md"
        if not p.exists():
            p.write_text(f"# {name}\n\nAuto-generated skill.\n", encoding="utf-8")
            created.append(name)
    return {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "created": created}


def list_skills() -> dict[str, Any]:
    """List all evolved skills stored in shared/skills."""
    skills_dir = COUNCIL_HOME / "shared" / "skills"
    if not skills_dir.exists():
        return {"skills": [], "count": 0}
    names = sorted(p.name for p in skills_dir.glob("*.md"))
    return {"skills": names, "count": len(names)}


def read_skill(name: str) -> dict[str, Any]:
    """Read a single skill by filename."""
    if "/" in name or "\\" in name or name.endswith(".."):
        return {"ok": False, "error": "invalid skill name"}
    p = COUNCIL_HOME / "shared" / "skills" / f"{name}.md"
    if not p.exists():
        return {"ok": False, "error": f"skill {name!r} not found"}
    return {"ok": True, "name": name, "content": p.read_text(encoding="utf-8", errors="ignore")}
