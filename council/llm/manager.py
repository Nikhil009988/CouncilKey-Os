"""CouncilKey-Os Local LLM Manager."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
LLM_DIR = COUNCIL_HOME / "llm"


def ensure_dirs() -> None:
    LLM_DIR.mkdir(parents=True, exist_ok=True)


def available() -> dict[str, Any]:
    ensure_dirs()
    providers = {
        "openai": os.environ.get("OPENAI_API_KEY"),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "openrouter": os.environ.get("OPENROUTER_API_KEY"),
        "nous": os.environ.get("NOUS_API_KEY"),
    }
    return {"providers": {k: bool(v) for k, v in providers.items()}, "default": "nous" if providers["nous"] else next((k for k, v in providers.items() if v), None)}
