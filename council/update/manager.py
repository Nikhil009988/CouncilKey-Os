"""CouncilKey-Os update manager."""
from __future__ import annotations

import os
from pathlib import Path

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore

# Canonical upstream repo for this project (was previously pointing at a stale fork).
DEFAULT_REPO = "Nikhil009988/CouncilKey-Os"
_REPO_ENV = "COUNCIL_UPDATE_REPO"
_ROOT = Path(__file__).resolve().parent.parent.parent


def current_version() -> str:
    """Read VERSION robustly (repo root, package parent, or cwd)."""
    for p in (_ROOT / "VERSION", Path(__file__).parent.parent.parent / "VERSION", Path("VERSION")):
        try:
            text = p.read_text(encoding="utf-8").strip()
            if text:
                return text
        except Exception:
            continue
    return "1.0.0-dev"


def _repo() -> str:
    return os.environ.get(_REPO_ENV, DEFAULT_REPO)


def check_update(repo: str | None = None) -> dict[str, object]:
    """Check GitHub releases for a newer version. Always includes `current`."""
    current = current_version()
    if httpx is None:
        return {"update_available": False, "current": current, "error": "httpx not installed"}
    try:
        r = httpx.get(
            f"https://api.github.com/repos/{repo or _repo()}/releases/latest",
            timeout=10,
            headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code == 404:
            return {"update_available": False, "current": current, "status": 404,
                    "error": f"repo {repo or _repo()} has no releases yet"}
        if r.status_code != 200:
            return {"update_available": False, "current": current, "status": r.status_code}
        data = r.json()
        latest = data.get("tag_name", current).lstrip("v")
        current_clean = current.lstrip("v")
        return {
            "update_available": latest != current_clean,
            "latest": latest,
            "current": current_clean,
            "repo": repo or _repo(),
            "url": data.get("html_url", ""),
            "name": data.get("name", ""),
        }
    except Exception as exc:
        return {"update_available": False, "current": current, "error": str(exc)}
