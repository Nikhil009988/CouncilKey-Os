"""CouncilKey-Os Ollama manager."""
from __future__ import annotations

import os
from typing import Any

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


def _base() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def _headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


def is_running() -> dict[str, object]:
    if httpx is None:
        return {"running": False, "error": "httpx not installed"}
    try:
        r = httpx.get(_base() + "/api/tags", timeout=3)
        r.raise_for_status()
        data = r.json()
        models = [m.get("name") for m in data.get("models", [])]
        return {"running": True, "models": models}
    except Exception as exc:
        return {"running": False, "error": str(exc)}


def chat(model: str, prompt: str, system: str = "") -> dict[str, object]:
    if httpx is None:
        return {"ok": False, "error": "httpx not installed"}
    payload: dict[str, object] = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    try:
        r = httpx.post(_base() + "/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return {"ok": True, "text": data.get("response", "")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def embeddings(model: str, text: str) -> dict[str, object]:
    if httpx is None:
        return {"ok": False, "error": "httpx not installed"}
    try:
        r = httpx.post(_base() + "/api/embeddings", json={"model": model, "prompt": text}, timeout=60)
        r.raise_for_status()
        data = r.json()
        return {"ok": True, "embedding": data.get("embedding", [])}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
