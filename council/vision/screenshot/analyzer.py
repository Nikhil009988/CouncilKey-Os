"""CouncilKey-Os Vision - screenshot + image analysis (real implementation).

Screenshot: PIL ImageGrab with CLI fallbacks (gnome-screenshot / scrot / ImageMagick).
Analysis: local Ollama vision model (qwen2.5vl / llava) when available.
"""
from __future__ import annotations

import base64
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
SHOT_DIR = COUNCIL_HOME / "hermes" / "cache" / "screenshots"

_CLI_TOOLS = (
    ["gnome-screenshot", "-f", None],
    ["scrot", None],
    ["import", "-window", "root", None],
)


def take_screenshot(name: str | None = None) -> dict[str, Any]:
    """Capture the desktop to a PNG inside the cache. Falls back across tools."""
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = SHOT_DIR / f"{name or 'shot'}-{ts}.png"

    try:
        from PIL import ImageGrab  # type: ignore

        img = ImageGrab.grab()
        img.save(path)
        return {"ok": True, "path": str(path), "size": path.stat().st_size}
    except Exception:
        pass

    for tool in _CLI_TOOLS:
        cmd = [str(path) if c is None else c for c in tool]
        try:
            subprocess.run(cmd, check=True, timeout=20, capture_output=True)
            if path.exists() and path.stat().st_size > 0:
                return {"ok": True, "path": str(path), "size": path.stat().st_size}
        except Exception:
            continue

    return {
        "ok": False,
        "error": "no screenshot tool available (install pillow, gnome-screenshot, scrot or imagemagick)",
    }


def analyze_screenshot(path: str | None = None, prompt: str = "Describe this screenshot in detail.") -> dict[str, Any]:
    """Analyze a screenshot with a local vision model (Ollama)."""
    if path and Path(path).exists():
        img_path = path
    else:
        shot = take_screenshot()
        if not shot.get("ok"):
            return shot
        img_path = shot["path"]

    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    try:
        tags = httpx.get(f"{base}/api/tags", timeout=3)
        tags.raise_for_status()
        models = [m.get("name", "") for m in tags.json().get("models", [])]
    except Exception as exc:
        return {"ok": False, "error": f"ollama unavailable: {exc}", "path": img_path}

    vision_model = next(
        (m for m in models if any(k in m.lower() for k in ("vl", "llava", "vision"))),
        None,
    )
    if not vision_model:
        return {
            "ok": False,
            "error": "no vision model installed (try: ollama pull llava:7b or qwen2.5vl:3b)",
            "path": img_path,
            "models": models,
        }

    try:
        b64 = base64.b64encode(Path(img_path).read_bytes()).decode()
        r = httpx.post(
            f"{base}/api/generate",
            json={"model": vision_model, "prompt": prompt, "images": [b64], "stream": False},
            timeout=180,
        )
        r.raise_for_status()
        return {"ok": True, "model": vision_model, "path": img_path, "analysis": r.json().get("response", "")}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": img_path}


def save_upload(raw: bytes, filename: str = "upload.png") -> dict[str, Any]:
    """Persist an uploaded image into the screenshot cache."""
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe = "".join(c for c in Path(filename).name if c.isalnum() or c in "._-")[:60]
    path = SHOT_DIR / f"upload-{ts}-{safe}"
    path.write_bytes(raw)
    return {"ok": True, "path": str(path), "size": len(raw)}


def vision_screenshot_tools() -> list[dict[str, str]]:
    """Tool descriptors for UI/agent documentation."""
    return [
        {"name": "screenshot", "description": "Take screenshot of desktop - implemented"},
        {"name": "vision_analyze", "description": "Analyze screenshot via local vision model - implemented"},
        {"name": "browser_dom_annotate", "description": "DOM annotation for precise browser control"},
        {"name": "computer_use", "description": "Full desktop control via AT-SPI/Wayland (optional host setup)"},
    ]


if __name__ == "__main__":
    import json

    print(json.dumps(take_screenshot(), indent=2))
