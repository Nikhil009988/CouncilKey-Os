"""CouncilKey-Os Skill Evolution."""
from __future__ import annotations

import os
import time
from pathlib import Path

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))


def evolve() -> dict[str, Any]:
    skills_dir = COUNCIL_HOME / "shared" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for name in ["council-reflection", "storage-health", "consensus-vote"]:
        p = skills_dir / f"{name}.md"
        if not p.exists():
            p.write_text(f"# {name}\n\nAuto-generated skill.\n", encoding="utf-8")
            created.append(name)
    return {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "created": created}
