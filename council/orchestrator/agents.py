"""CouncilKey-Os production agent adapters.

Each adapter talks to a local agent gateway (Hermes / OpenClaw / Agent-Zero).
If a gateway is unreachable the adapter degrades to a deterministic mock
response instead of crashing the council, and a circuit breaker avoids
hammering a dead gateway.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

COUNCIL_HOME = os.environ.get("COUNCIL_HOME", "/var/lib/council")


@dataclass
class AgentResult:
    agent: str
    role: str
    response: str
    latency: float
    status: str


class AgentClient(Protocol):
    async def ask(self, prompt: str, timeout: float = 60.0) -> AgentResult:
        ...


class _CircuitBreaker:
    def __init__(self, threshold: int = 3, window: float = 60.0):
        self.failures = 0
        self.threshold = threshold
        self.window = window
        self.opened_at = 0.0

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()

    def allow(self) -> bool:
        if self.failures < self.threshold:
            return True
        if time.monotonic() - self.opened_at > self.window:
            self.failures = 0
            return True
        return False


def _mock(agent: str, role: str, prompt: str, exc: Exception | None = None) -> AgentResult:
    detail = f": {exc}" if exc else ""
    return AgentResult(agent, role, f"[mock fallback] {prompt}", 0.0, f"offline (mock){detail}")


class HermesClient:
    def __init__(self, base_url: str = "http://127.0.0.1:18790", token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("HERMES_TOKEN") or _read_gateway_token("hermes")
        self.cb = _CircuitBreaker()

    async def ask(self, prompt: str, timeout: float = 60.0) -> AgentResult:
        if not self.cb.allow():
            return _mock("hermes", "memory", prompt)
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    f"{self.base_url}/api/message",
                    json={"text": prompt},
                    headers=self._headers(),
                )
                r.raise_for_status()
                data = r.json()
                text = data.get("text") or data.get("response") or str(data)
                return AgentResult("hermes", "memory", text, time.monotonic() - start, "live")
        except Exception as exc:
            self.cb.record_failure()
            return _mock("hermes", "memory", prompt, exc)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {"Content-Type": "application/json"}
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}


class OpenClawClient:
    def __init__(self, base_url: str = "http://127.0.0.1:18789"):
        self.base_url = base_url.rstrip("/")
        self.token = os.environ.get("OPENCLAW_TOKEN") or _read_gateway_token("openclaw")
        self.cb = _CircuitBreaker()

    async def ask(self, prompt: str, timeout: float = 60.0) -> AgentResult:
        if not self.cb.allow():
            return _mock("openclaw", "action", prompt)
        start = time.monotonic()
        endpoints = [f"{self.base_url}/api/message", f"{self.base_url}/api/v1/chat"]
        last_exc: Exception | None = None
        for ep in endpoints:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    r = await client.post(ep, json={"text": prompt}, headers=self._headers())
                    r.raise_for_status()
                    data = r.json()
                    text = data.get("text") or data.get("reply") or data.get("response") or str(data)
                    return AgentResult("openclaw", "action", text, time.monotonic() - start, "live")
            except Exception as exc:
                last_exc = exc
        self.cb.record_failure()
        return _mock("openclaw", "action", prompt, last_exc)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {"Content-Type": "application/json"}
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}


class AgentZeroClient:
    def __init__(self, base_url: str = "http://127.0.0.1:50001"):
        self.base_url = base_url.rstrip("/")
        self.cb = _CircuitBreaker()

    async def ask(self, prompt: str, timeout: float = 120.0) -> AgentResult:
        if not self.cb.allow():
            return _mock("agent-zero", "builder", prompt)
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(
                    f"{self.base_url}/api/message",
                    json={"text": prompt, "context": {}},
                )
                r.raise_for_status()
                data = r.json()
                text = data.get("text") or data.get("response") or str(data)
                return AgentResult("agent-zero", "builder", text, time.monotonic() - start, "live")
        except Exception as exc:
            self.cb.record_failure()
            return _mock("agent-zero", "builder", prompt, exc)


def _read_gateway_token(agent: str) -> str | None:
    candidates = [
        Path.home() / f".{agent}" / "gateway.token",
        Path(COUNCIL_HOME) / agent / "gateway.token",
        Path("/run/secrets") / f"{agent}_token",
    ]
    for p in candidates:
        try:
            if p.exists():
                with open(p, encoding="utf-8") as fh:
                    token = fh.read().strip()
                if token:
                    return token
        except Exception:
            continue
    return None


def build_default_clients() -> dict[str, AgentClient]:
    return {
        "hermes": HermesClient(),
        "openclaw": OpenClawClient(),
        "agent-zero": AgentZeroClient(),
    }
