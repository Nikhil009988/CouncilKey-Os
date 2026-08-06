"""Local LLM agents - three role agents powered by Ollama (real local inference).

This is the default brain of the council: instead of depending on three
external gateway servers that rarely run, the council asks a local LLM
(Ollama) three times, once per role:

- hermes     -> memory & analysis  (qwen2.5:3b)
- openclaw   -> action & execution (qwen2.5:3b)
- agent-zero -> builder & code     (deepseek-coder:1.3b, falls back to qwen2.5:3b)

Every agent gets a distinct system prompt, so three real, different answers
are produced for the council to vote on. If Ollama is not installed/running,
the orchestrator degrades to an explicitly-labelled mock client.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from council.orchestrator.agents import AgentResult

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# model -> (size, role, description) - same catalog as council.llm.ollama
RECOMMENDED_MODELS = {
    "qwen2.5:3b": "Best balance of size/smartness for CPU: 3B params, 32k context, tool calling",
    "qwen2.5:1.5b": "Lighter 1.5B model - fast on weak CPUs",
    "deepseek-coder:1.3b": "Specialized code model for the builder agent",
}

ROLE_AGENTS: dict[str, dict[str, Any]] = {
    "hermes": {
        "role": "memory",
        "model": "qwen2.5:3b",
        "temperature": 0.4,
        "system": (
            "You are Hermes, the memory and analysis agent of a council of three AI agents. "
            "You analyze requests carefully: goals, constraints, risks, missing information, "
            "and relevant context from past experience. You are precise, structured and cautious. "
            "Answer the user's request with your analysis."
        ),
    },
    "openclaw": {
        "role": "action",
        "model": "qwen2.5:3b",
        "temperature": 0.5,
        "system": (
            "You are OpenClaw, the action and execution agent of a council of three AI agents. "
            "You produce concrete, step-by-step action plans with specific commands and "
            "deliverables. You are direct, practical and execution-focused. "
            "Answer the user's request with your actionable plan."
        ),
    },
    "agent-zero": {
        "role": "builder",
        "model": "deepseek-coder:1.3b",
        "temperature": 0.4,
        "system": (
            "You are Agent Zero, the builder and review agent of a council of three AI agents. "
            "You review plans for safety, correctness and completeness, and you write the final "
            "polished answer. You are rigorous about safety and details. "
            "Answer the user's request with your reviewed, final answer."
        ),
    },
}

DEFAULT_MODEL = "qwen2.5:3b"


def ollama_available() -> bool:
    """Quick check that an Ollama server answers on /api/tags."""
    try:
        r = httpx.get(OLLAMA_BASE.rstrip("/") + "/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


_models_cache: tuple[float, list[str]] | None = None
_MODELS_TTL = 10.0  # seconds - don't hammer /api/tags on every agent ask


def installed_models(force: bool = False) -> list[str]:
    """List models installed in Ollama, cached for a few seconds."""
    global _models_cache
    now = time.monotonic()
    if not force and _models_cache and now - _models_cache[0] < _MODELS_TTL:
        return _models_cache[1]
    try:
        r = httpx.get(OLLAMA_BASE.rstrip("/") + "/api/tags", timeout=2.0)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            _models_cache = (now, models)
            return models
    except Exception:
        pass
    _models_cache = (now, [])
    return []


def pick_model(preferred: str, available: list[str]) -> str:
    """Use the preferred model when installed, else the first available one."""
    if preferred in available:
        return preferred
    for fallback in (DEFAULT_MODEL,):
        if fallback in available:
            return fallback
    return available[0] if available else DEFAULT_MODEL


class OllamaAgentClient:
    """An agent client that asks a local Ollama model with a role system prompt."""

    def __init__(self, agent: str, base_url: str | None = None):
        self.agent = agent
        self.cfg = ROLE_AGENTS[agent]
        self.base_url = (base_url or OLLAMA_BASE).rstrip("/")

    async def ask(self, prompt: str, timeout: float = 180.0) -> AgentResult:
        start = time.monotonic()
        model = pick_model(self.cfg["model"], installed_models())
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    self.base_url + "/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "system": self.cfg["system"],
                        "stream": False,
                        "options": {"temperature": self.cfg["temperature"], "num_predict": 512},
                    },
                )
                r.raise_for_status()
                text = (r.json().get("response") or "").strip()
                return AgentResult(
                    agent=self.agent,
                    role=self.cfg["role"],
                    response=text or "(empty response)",
                    latency=time.monotonic() - start,
                    status=f"local-llm ({model})",
                )
        except Exception as exc:
            return AgentResult(
                agent=self.agent,
                role=self.cfg["role"],
                response=f"[local-llm unavailable: {exc}]",
                latency=time.monotonic() - start,
                status=f"error ({exc})",
            )


class MockAgentClient:
    """Explicit, clearly-labelled offline client used only when no real backend exists."""

    def __init__(self, agent: str):
        self.agent = agent
        self.role = ROLE_AGENTS[agent]["role"]

    async def ask(self, prompt: str, timeout: float = 60.0) -> AgentResult:
        return AgentResult(
            agent=self.agent,
            role=self.role,
            response=f"[mock fallback] {prompt}",
            latency=0.0,
            status="offline (mock) - run 'councilkey setup' to add an API key, or start the agent gateway",
        )
