"""Provider-based AI client for the three council roles.

The council's three role agents (Hermes / OpenClaw / Agent Zero) answer using
a model provider configured during setup - the API key is stored in the
encrypted secrets vault (or env) and read at request time.

Supported providers:
- openai      (https://api.openai.com/v1)                 gpt-4o-mini
- openrouter  (https://openrouter.ai/api/v1)              openrouter/auto
- gemini      (https://generativelanguage.googleapis.com/v1beta/openai)  gemini-2.0-flash
- anthropic   (https://api.anthropic.com/v1/messages)     claude-3-5-haiku-latest

Base URLs can be overridden via OPENAI_BASE_URL / OPENROUTER_BASE_URL /
GEMINI_BASE_URL / ANTHROPIC_BASE_URL (used by tests and self-hosted
compatible gateways).
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from council.orchestrator.agents import AgentResult
from council.secrets.vault import get_secret

# provider -> config
PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "auth": "bearer",
        "protocol": "openai",
    },
    "openrouter": {
        "name": "OpenRouter",
        "env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/auto",
        "auth": "bearer",
        "protocol": "openai",
    },
    "gemini": {
        "name": "Google Gemini",
        "env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "auth": "bearer",
        "protocol": "openai",
    },
    "anthropic": {
        "name": "Anthropic",
        "env": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1/messages",
        "model": "claude-3-5-haiku-latest",
        "auth": "x-api-key",
        "protocol": "anthropic",
    },
}

# role -> (role label, system prompt) - same roles as the council
ROLE_SYSTEMS: dict[str, str] = {
    "hermes": (
        "You are Hermes, the memory and analysis agent of a council of three AI agents. "
        "Analyze requests carefully: goals, constraints, risks, missing information, and "
        "relevant context from past experience. You are precise, structured and cautious. "
        "Answer the user's request with your analysis."
    ),
    "openclaw": (
        "You are OpenClaw, the action and execution agent of a council of three AI agents. "
        "Produce concrete, step-by-step action plans with specific commands and deliverables. "
        "You are direct, practical and execution-focused. Answer with your actionable plan."
    ),
    "agent-zero": (
        "You are Agent Zero, the builder and review agent of a council of three AI agents. "
        "Review plans for safety, correctness and completeness, and write the final polished "
        "answer. You are rigorous about safety and details. Answer with your reviewed final answer."
    ),
}

# per-role model override (optional)
ROLE_MODELS: dict[str, str] = {
    "agent-zero": "openrouter/auto",  # placeholder - only used when provider=openrouter
}

_provider_cache: tuple[float, str | None] | None = None
_PROVIDER_TTL = 5.0


def _key_for(provider: str) -> str | None:
    """Find the API key: env first, then the encrypted vault."""
    env = PROVIDERS[provider]["env"]
    env_val = os.environ.get(env)
    if env_val:
        return env_val
    try:
        return get_secret(env)
    except Exception:
        return None


def active_provider() -> str | None:
    """The provider with a key available (env or vault). Cached briefly."""
    global _provider_cache
    now = time.monotonic()
    if _provider_cache and now - _provider_cache[0] < _PROVIDER_TTL:
        return _provider_cache[1]
    for name in ("openai", "openrouter", "gemini", "anthropic"):
        if _key_for(name):
            _provider_cache = (now, name)
            return name
    _provider_cache = (now, None)
    return None


def configured_provider() -> dict[str, Any] | None:
    """Details of the active provider (or None)."""
    name = active_provider()
    if not name:
        return None
    return {**PROVIDERS[name], "id": name}


def provider_status() -> dict[str, Any]:
    """Status for the dashboard: which providers have keys."""
    status = {}
    for name, cfg in PROVIDERS.items():
        status[name] = {
            "configured": _key_for(name) is not None,
            "model": cfg["model"],
            "name": cfg["name"],
        }
    active = active_provider()
    return {"providers": status, "active": active, "active_model": PROVIDERS[active]["model"] if active else None}


class ProviderAgentClient:
    """An agent client that asks the configured model provider with a role
    system prompt. Uses the same provider for all roles (distinct voices via
    the system prompts); a per-role model override can be added later."""

    def __init__(self, agent: str, provider: str | None = None, base_url: str | None = None):
        self.agent = agent
        self.provider = provider or active_provider()
        if self.provider not in PROVIDERS:
            raise ValueError(f"unknown provider {self.provider!r}")
        self.cfg = PROVIDERS[self.provider]
        self.base_url = base_url or os.environ.get(
            self.cfg["env"].replace("_API_KEY", "_BASE_URL"), self.cfg["base_url"]
        ).rstrip("/")
        self.key = _key_for(self.provider)

    async def ask(self, prompt: str, timeout: float = 120.0) -> AgentResult:
        start = time.monotonic()
        if not self.key:
            return AgentResult(
                self.agent, "?", f"[no API key for {self.provider}]",
                0.0, f"missing {self.cfg['env']}",
            )
        system = ROLE_SYSTEMS.get(self.agent, "")
        model = self.cfg["model"]
        try:
            if self.cfg["protocol"] == "anthropic":
                text = await self._ask_anthropic(prompt, system, model, timeout)
            else:
                text = await self._ask_openai_compat(prompt, system, model, timeout)
            return AgentResult(
                agent=self.agent,
                role="council-role",
                response=text or "(empty response)",
                latency=time.monotonic() - start,
                status=f"{self.provider} ({model})",
            )
        except Exception as exc:
            return AgentResult(
                self.agent, "council-role",
                f"[provider error: {exc}]",
                time.monotonic() - start,
                f"error ({exc})",
            )

    async def _ask_openai_compat(self, prompt: str, system: str, model: str, timeout: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/Nikhil009988/CouncilKey-Os"
            headers["X-Title"] = "CouncilKey-Os"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 700,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(self.base_url + "/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "")

    async def _ask_anthropic(self, prompt: str, system: str, model: str, timeout: float) -> str:
        headers = {
            "x-api-key": self.key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "system": system,
            "max_tokens": 700,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(self.base_url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
