"""CouncilKey-Os Ollama manager with model management."""
from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import httpx
except Exception:
    httpx = None

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
OLLAMA_MODELS_DIR = COUNCIL_HOME / "models" / "ollama"

RECOMMENDED_MODELS = {
    "qwen2.5:3b": {"size": "1.9GB", "role": "general", "description": "Best balance size/smart: 3B params, 32k context, tool calling, coding"},
    "deepseek-coder:1.3b": {"size": "0.8GB", "role": "code", "description": "Specialized code model for the Codex builder role"},
    "nomic-embed-text": {"size": "274MB", "role": "embeddings", "description": "Embedding model for LanceDB RAG"},
    "qwen2.5:7b": {"size": "4.7GB", "role": "general", "description": "Smarter 7B model if storage allows"},
    "llama3.2:3b": {"size": "2.0GB", "role": "general", "description": "Meta's Llama 3.2 3B"},
    "phi3:3.8b": {"size": "2.3GB", "role": "general", "description": "Microsoft Phi-3 small"},
}


def _base() -> str:
    return OLLAMA_BASE


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


def pull(model: str) -> dict[str, object]:
    if httpx is None:
        return {"ok": False, "error": "httpx not installed"}
    try:
        # Stream the pull response
        with httpx.stream("POST", _base() + "/api/pull", json={"model": model}, timeout=300) as r:
            r.raise_for_status()
            last_status = ""
            for line in r.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        status = data.get("status", "")
                        if status:
                            last_status = status
                    except Exception:
                        pass
        return {"ok": True, "status": last_status}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def delete(model: str) -> dict[str, object]:
    if httpx is None:
        return {"ok": False, "error": "httpx not installed"}
    try:
        r = httpx.delete(_base() + "/api/delete", json={"model": model}, timeout=30)
        r.raise_for_status()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def list_models() -> dict[str, object]:
    status = is_running()
    if not status.get("running"):
        return {"ok": False, "models": [], "error": status.get("error")}
    models = status.get("models", [])
    return {
        "ok": True,
        "models": [
            {
                "name": m,
                "recommended": m in RECOMMENDED_MODELS,
                "info": RECOMMENDED_MODELS.get(m, {})
            }
            for m in models
        ],
        "recommended": RECOMMENDED_MODELS
    }


def ensure_models(models: list[str] | None = None) -> dict[str, object]:
    """Ensure recommended models are available, pull if missing."""
    if models is None:
        models = ["qwen2.5:3b", "deepseek-coder:1.3b", "nomic-embed-text"]
    
    status = is_running()
    if not status.get("running"):
        return {"ok": False, "error": "Ollama not running", "pulled": []}
    
    available = set(status.get("models", []))
    pulled = []
    for model in models:
        if model not in available:
            result = pull(model)
            if result.get("ok"):
                pulled.append(model)
            else:
                return {"ok": False, "error": f"Failed to pull {model}: {result.get('error')}", "pulled": pulled}
    return {"ok": True, "pulled": pulled, "available": list(available)}


def get_model_info(model: str) -> dict[str, object]:
    """Get detailed info about a model."""
    if httpx is None:
        return {"ok": False, "error": "httpx not installed"}
    try:
        r = httpx.post(_base() + "/api/show", json={"model": model}, timeout=10)
        r.raise_for_status()
        return {"ok": True, "info": r.json()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_model_defaults() -> dict[str, object]:
    """Get default model assignments for council agents."""
    return {
        "hermes": "qwen2.5:3b",
        "openclaw": "qwen2.5:3b",
        "codex": "deepseek-coder:1.3b",
        "embeddings": "nomic-embed-text",
        "llm_judge": "qwen2.5:7b"  # fallback to qwen2.5:3b if not available
    }