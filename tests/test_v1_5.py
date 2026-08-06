"""CouncilKey-Os v1.5 - interactive setup wizard + provider client tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_wizard_providers_defined():
    from council.agents.setup_wizard import PROVIDERS

    assert set(PROVIDERS) == {"openai", "anthropic", "gemini", "openrouter", "none"}
    assert PROVIDERS["openai"]["env"] == "OPENAI_API_KEY"
    assert PROVIDERS["openai"]["choice"] == "openai-api-key"
    assert PROVIDERS["anthropic"]["choice"] == "anthropic-api-key"


def test_wizard_noninteractive_runs():
    """councilkey setup --provider none --no-agents --skip-tests
    must complete without hanging (no prompts in flag mode)."""
    import subprocess

    r = subprocess.run(
        [str(ROOT / ".venv/bin/councilkey"), "setup",
         "--provider", "none", "--no-agents", "--skip-tests"],
        capture_output=True, text=True, timeout=120,
    )
    assert "Setup finished" in r.stdout
    assert r.returncode == 0, r.stdout[-400:]


def test_wizard_stores_key_in_vault(monkeypatch):
    from council.agents import setup_wizard as w
    from council.secrets.vault import get_secret

    w._store_key("OPENAI_API_KEY", "sk-test-xyz")
    assert get_secret("OPENAI_API_KEY") == "sk-test-xyz"


def test_configure_openclaw_missing_binary():
    from council.agents.setup_wizard import _configure_openclaw

    r = _configure_openclaw("openai", "sk-test")
    assert isinstance(r, dict)
    assert "ok" in r


def test_agents_env_prints_exports():
    import subprocess

    r = subprocess.run(
        [str(ROOT / ".venv/bin/councilkey"), "agents", "env"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0
    assert ("export " in r.stdout) or ("no API keys" in r.stdout)


# ------------------------------------------------------------ provider client
def test_provider_catalog():
    from council.llm.provider import PROVIDERS, ROLE_SYSTEMS

    assert set(PROVIDERS) == {"openai", "openrouter", "gemini", "anthropic"}
    assert set(ROLE_SYSTEMS) == {"hermes", "openclaw", "agent-zero"}
    assert PROVIDERS["openai"]["protocol"] == "openai"
    assert PROVIDERS["anthropic"]["protocol"] == "anthropic"


def test_provider_agent_ask_openai(monkeypatch):
    """The provider client calls the OpenAI-compatible endpoint and returns the
    role answer - verified with a mocked transport."""
    import httpx

    from council.llm import provider as p

    monkeypatch.setattr(p, "active_provider", lambda: "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import json

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["model"] == "gpt-4o-mini"
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hermes analysis: safe plan."}}]})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return original(transport=transport, **kwargs)

    monkeypatch.setattr(p.httpx, "AsyncClient", factory)

    import asyncio

    client = p.ProviderAgentClient("hermes", provider="openai")
    result = asyncio.run(client.ask("plan a trip"))
    assert "safe plan" in result.response
    assert result.status.startswith("openai")


def test_provider_agent_anthropic(monkeypatch):
    import httpx

    from council.llm import provider as p

    monkeypatch.setattr(p, "active_provider", lambda: "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    import json

    async def handler(request: httpx.Request) -> httpx.Response:
        assert "x-api-key" in request.headers
        body = json.loads(request.content)
        assert body["model"] == "claude-3-5-haiku-latest"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Anthropic reply ok"}]})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return original(transport=transport, **kwargs)

    monkeypatch.setattr(p.httpx, "AsyncClient", factory)

    import asyncio

    client = p.ProviderAgentClient("openclaw", provider="anthropic")
    result = asyncio.run(client.ask("hi"))
    assert "Anthropic reply ok" in result.response
    assert result.status.startswith("anthropic")


def test_provider_agent_no_key(monkeypatch):
    from council.llm import provider as p

    monkeypatch.setattr(p, "active_provider", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # ignore the vault too (other tests may have stored a key)
    monkeypatch.setattr(p, "_key_for", lambda n: None)

    import asyncio

    client = p.ProviderAgentClient("hermes", provider="openai")
    result = asyncio.run(client.ask("hi"))
    assert "no API key" in result.response


def test_provider_status_shape(monkeypatch):
    from council.llm import provider as p

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    status = p.provider_status()
    assert set(status["providers"]) == {"openai", "openrouter", "gemini", "anthropic"}
    assert status["active"] in (None, "openai", "openrouter", "gemini", "anthropic")


def test_client_modes_provider(monkeypatch):
    """With a provider key set (no gateway), modes = provider."""
    from council.llm import provider as p
    from council.orchestrator import agents as oa

    monkeypatch.setattr(p, "active_provider", lambda: "openai")
    monkeypatch.setattr(p, "_key_for", lambda n: "sk-x" if n == "openai" else None)
    monkeypatch.setattr(oa, "gateway_reachable", lambda *a, **k: False)
    modes = oa.client_modes()
    assert all(m["mode"] == "provider" for m in modes.values())


def test_client_modes_mock(monkeypatch):
    from council.llm import provider as p
    from council.orchestrator import agents as oa

    monkeypatch.setattr(p, "active_provider", lambda: None)
    monkeypatch.setattr(oa, "gateway_reachable", lambda *a, **k: False)
    modes = oa.client_modes()
    assert all(m["mode"] == "mock" for m in modes.values())
