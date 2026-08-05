"""CouncilKey-Os v1.4 - local-LLM agents (real working brains) tests."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _fake_ollama_env(monkeypatch):
    """Point the LLM modules at a fake-but-available Ollama."""
    monkeypatch.setattr("council.llm.agents.ollama_available", lambda: True)
    monkeypatch.setattr("council.llm.agents.installed_models", lambda: ["qwen2.5:3b", "deepseek-coder:1.3b"])


def _fake_async_client(monkeypatch, handler):
    """Replace httpx.AsyncClient with one that uses the given MockTransport."""
    import httpx

    from council.llm import agents as la

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient  # keep the real class to avoid recursion

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return original(transport=transport, **kwargs)

    monkeypatch.setattr(la.httpx, "AsyncClient", factory)


def test_ollama_agent_ask_returns_real_answer(monkeypatch):
    """The Ollama agent client really calls the LLM and returns its text."""
    import httpx

    from council.llm import agents as la

    _fake_ollama_env(monkeypatch)

    import json

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen2.5:3b"
        assert body["system"]  # role system prompt is sent
        return httpx.Response(200, json={"response": "As Hermes, I analyze: the plan is safe and clear."})

    _fake_async_client(monkeypatch, handler)

    client = la.OllamaAgentClient("hermes")
    result = asyncio.run(client.ask("plan a trip"))
    assert result.agent == "hermes"
    assert result.role == "memory"
    assert "plan is safe" in result.response
    assert result.status.startswith("local-llm")


def test_ollama_agent_picks_installed_model(monkeypatch):
    import httpx

    from council.llm import agents as la

    # only deepseek-coder installed -> hermes falls back to it
    monkeypatch.setattr("council.llm.agents.installed_models", lambda: ["deepseek-coder:1.3b"])

    import json

    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["model"] == "deepseek-coder:1.3b"
        return httpx.Response(200, json={"response": "ok"})

    _fake_async_client(monkeypatch, handler)
    result = asyncio.run(la.OllamaAgentClient("hermes").ask("hi"))
    assert result.status.startswith("local-llm")


def test_mock_agent_client_is_explicit(monkeypatch):
    from council.llm import agents as la

    monkeypatch.setattr("council.llm.agents.ollama_available", lambda: False)
    client = la.MockAgentClient("openclaw")
    result = asyncio.run(client.ask("hi"))
    assert "mock" in result.status
    assert result.role == "action"


def test_client_modes_without_backends_is_mock(monkeypatch):
    from council.orchestrator import agents as oa

    monkeypatch.setattr("council.llm.agents.ollama_available", lambda: False)
    modes = oa.client_modes()
    assert set(modes) == {"hermes", "openclaw", "agent-zero"}
    assert all(m["mode"] == "mock" for m in modes.values())


def test_client_modes_with_ollama_is_local_llm(monkeypatch):
    from council.orchestrator import agents as oa

    monkeypatch.setattr("council.llm.agents.ollama_available", lambda: True)
    modes = oa.client_modes()
    assert all(m["mode"] == "local-llm" for m in modes.values())


def test_build_default_clients_fallback(monkeypatch):
    from council.llm import agents as la
    from council.orchestrator import agents as oa

    monkeypatch.setattr("council.llm.agents.ollama_available", lambda: True)
    clients = oa.build_default_clients()
    assert all(isinstance(c, la.OllamaAgentClient) for c in clients.values())

    monkeypatch.setattr("council.llm.agents.ollama_available", lambda: False)
    clients = oa.build_default_clients()
    assert all(isinstance(c, la.MockAgentClient) for c in clients.values())


def test_api_status_has_modes():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    data = client.get("/api/status").json()
    for name in ("hermes", "openclaw", "agent-zero"):
        assert name in data["agents"]
        assert data["agents"][name]["mode"] in ("gateway", "local-llm", "mock")
    assert "models" in data["ollama"]


def test_openclaw_prebuilt_cli_step():
    from council.agents.installer import _install_openclaw_cli

    assert callable(_install_openclaw_cli)


def test_windows_scripts_exist():
    for rel in ("scripts/setup.ps1", "scripts/start.ps1", "scripts/start.bat"):
        assert (ROOT / rel).exists(), rel


def test_three_d_route_importable_and_served():
    """The 3D dashboard is importable (package name '3d' can't be imported
    normally) and served at /3d on the main app."""
    from fastapi.testclient import TestClient

    from council.dashboard.three_d import create_app_3d

    standalone = TestClient(create_app_3d())
    r = standalone.get("/")
    assert r.status_code == 200
    assert "three.min.js" in r.text

    from council.orchestrator.main import app

    m = TestClient(app)
    r2 = m.get("/3d")
    assert r2.status_code == 200
    assert "three.min.js" in r2.text
