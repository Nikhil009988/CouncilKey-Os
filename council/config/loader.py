"""CouncilKey-Os config loader + validation."""
from __future__ import annotations

import os
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional
    yaml = None  # type: ignore

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
CONFIG_PATH = COUNCIL_HOME / "council" / "council.yaml"


def _defaults() -> dict[str, object]:
    return {
        "council": {
            "mode": "debate",
            "agents": {
                "hermes": {"weight": 1, "timeout": 60},
                "openclaw": {"weight": 1, "timeout": 60},
                "agent-zero": {"weight": 1, "timeout": 120},
            },
            "consensus": {"strategy": "majority", "min_agreement": 2},
            # --- v1.2 advanced orchestration settings ---
            "memory_injection": True,           # inject relevant journal/knowledge context
            "cache": {                           # semantic result cache
                "enabled": True,
                "ttl_seconds": 3600,
                "max_entries": 500,
            },
            "debate": {"default_rounds": 3},     # iterative debate rounds
            "decomposer": {"enabled": True},     # task decomposition
        }
    }


def load() -> dict[str, object]:
    if CONFIG_PATH.exists():
        try:
            text = CONFIG_PATH.read_text(encoding="utf-8")
            if yaml is not None:
                data = yaml.safe_load(text)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return _defaults()


def save(data: dict[str, object]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        CONFIG_PATH.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:
        CONFIG_PATH.write_text(str(data), encoding="utf-8")
