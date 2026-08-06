"""CouncilKey-Os v1.5 - interactive setup wizard + provider client tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from conftest import cli_path  # noqa: E402

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
        [str(cli_path()), "setup",
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
        [str(cli_path()), "agents", "env"],
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


def test_cli_ask_together():
    """councilkey ask must run all 3 agents and print votes (mock mode ok)."""
    import subprocess

    r = subprocess.run(
        [str(cli_path()), "ask", "ping"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stdout[-300:]
    assert "votes:" in r.stdout
    assert "hermes" in r.stdout and "openclaw" in r.stdout and "agent-zero" in r.stdout


def test_cli_ask_alone():
    import subprocess

    r = subprocess.run(
        [str(cli_path()), "ask", "ping", "--alone", "openclaw"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0
    assert "single agent answer: openclaw" in r.stdout


def test_agents_include_crewai_aider():
    """CrewAI (4th) and Aider (5th) are registered optional agents."""
    from council.agents.installer import AGENTS

    assert "crewai" in AGENTS and "aider" in AGENTS
    assert AGENTS["crewai"]["install"] == "pip"
    assert AGENTS["crewai"]["package"] == "crewai"
    assert AGENTS["aider"]["install"] == "pip"
    assert AGENTS["aider"]["package"] == "aider-chat"


def test_agent_zero_no_docker_install():
    """Agent Zero installs like hermes/openclaw: source + venv, no Docker."""
    from council.agents.installer import AGENTS

    assert AGENTS["agent-zero"]["install"] == "source-venv"
    # runtime note says docker is optional, not required
    assert "no Docker needed" in AGENTS["agent-zero"]["runtime"]
    assert "required" not in AGENTS["agent-zero"]["runtime"]


def test_pendrive_script_exists_and_syntax():
    import subprocess

    for rel in ("scripts/pendrive-setup.sh",):
        subprocess.run(["bash", "-n", str(ROOT / rel)], check=True)


def test_proc_resolves_windows_suffixes(monkeypatch):
    """Windows: bare 'npm' -> npm.cmd resolution (fixes WinError 2)."""
    from council.agents import proc

    # simulate Windows PATHEXT lookup for a missing bare command
    monkeypatch.setattr(proc.shutil, "which", lambda c: None)
    monkeypatch.setattr(proc.os, "name", "nt")
    monkeypatch.setattr(proc.os, "environ", {"PATHEXT": ".COM;.EXE;.BAT;.CMD"})
    # fake that npm.cmd exists
    def fake_which(cmd):
        if cmd.lower().endswith(".cmd"):
            return "C:\\Program Files\\nodejs\\npm.cmd"
        return None
    monkeypatch.setattr(proc.shutil, "which", fake_which)
    assert proc.which_resolved("npm") == "C:\\Program Files\\nodejs\\npm.cmd"


def test_run_cmd_resolves_executable(monkeypatch):
    """run_cmd resolves the command through which_resolved."""
    import subprocess as sp

    from council.agents import proc

    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return sp.CompletedProcess(cmd, 0, stdout="ok", stderr="")
    monkeypatch.setattr(proc.subprocess, "run", fake_run)
    monkeypatch.setattr(proc, "which_resolved", lambda c: "/usr/bin/" + c)
    ok, out = proc.run_cmd(["npm", "--version"], timeout=10)
    assert ok and out == "ok"
    assert captured["cmd"][0] == "/usr/bin/npm"


# ----------------------------------------------------- regression tests
def test_verify_only_checks_council_roles(monkeypatch):
    """agents verify must only ask the 3 council roles - crewai/aider are
    external CLIs and caused KeyError crashes before."""
    from council.orchestrator.agents import build_default_clients, client_modes

    monkeypatch.setattr("council.llm.provider.active_provider", lambda: None)
    monkeypatch.setattr("council.orchestrator.agents.gateway_reachable", lambda *a, **k: False)
    modes = client_modes()
    clients = build_default_clients()
    # invariant: clients and modes are exactly the 3 council roles
    assert set(clients) == {"hermes", "openclaw", "agent-zero"}
    assert set(modes) == {"hermes", "openclaw", "agent-zero"}


def test_configure_openclaw_success_with_nonzero_exit(monkeypatch):
    """openclaw onboard exits non-zero when its gateway is down but STILL
    writes the config - success must be detected from the output."""
    from council.agents import setup_wizard as w

    captured = {}

    def fake_run_cmd(cmd, **kw):
        captured["cmd"] = cmd
        return (False, "Refreshed plugin\nUpdated config: ~/.openclaw/openclaw.json\nWorkspace OK")

    monkeypatch.setattr(w, "run_cmd", fake_run_cmd)
    monkeypatch.setattr("shutil.which", lambda c: "/usr/bin/openclaw")
    r = w._configure_openclaw("openai", "sk-test")
    assert r["ok"] is True, r


def test_wizard_unwritable_home_graceful(monkeypatch, tmp_path):
    """Unwritable COUNCIL_HOME -> clear error + exit 1, no traceback."""
    from council.agents import setup_wizard as w

    monkeypatch.setattr(w, "COUNCIL_HOME", tmp_path / "no" / "such" / "nested" / "deep")
    # the mkdir will fail because 'no' doesn't exist? no - parents=True creates it.
    # force failure with a file in the way
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    monkeypatch.setattr(w, "COUNCIL_HOME", blocker / "child")

    # run_wizard should return 1 without raising
    rc = w.run_wizard(provider="none", no_agents=True, skip_tests=True)
    assert rc == 1


def test_vault_set_secret_no_crash_on_bad_path(monkeypatch, tmp_path):
    """vault.set_secret returns an error dict instead of raising when the
    vault cannot be written."""
    from council.secrets import vault

    monkeypatch.setattr(vault, "VAULT_PATH", tmp_path / "no-such-dir" / "vault.json")
    # make the parent path uncreatable by placing a FILE where the dir goes
    (tmp_path / "no-such-dir").write_text("file in the way")
    r = vault.set_secret("K", "v")
    assert r.get("ok") is False
    assert "error" in r


def test_npm_installer_resolves_windows_path(monkeypatch):
    """_install_npm uses the RESOLVED npm path (fixes WinError 2)."""
    from council.agents import installer as inst

    captured = {"cmds": []}
    def fake_run(cmd, cwd=None, timeout=900):
        captured["cmds"].append(cmd)
        return (True, "OpenClaw 2026.7.1-2")
    monkeypatch.setattr(inst, "_run", fake_run)
    # patch the module the function imports from (proc.which_resolved)
    monkeypatch.setattr("council.agents.proc.which_resolved", lambda c: "C:\\Program Files\\nodejs\\npm.cmd" if c == "npm" else None)
    monkeypatch.setattr("council.agents.proc.resolve_cmd", lambda c: c)
    monkeypatch.setattr("shutil.which", lambda c: True)
    r = inst._install_npm({"package": "openclaw@latest", "bin": "openclaw"})
    assert r["ok"] is True
    # first call is the npm install with the RESOLVED npm.cmd path
    assert captured["cmds"][0][0] == "C:\\Program Files\\nodejs\\npm.cmd"
    assert "install" in captured["cmds"][0]


def test_hermes_pip_fallback(monkeypatch):
    """hermes install falls back to pip when the official domain is down."""
    from council.agents import installer as inst

    class FakeHttpx:
        @staticmethod
        def get(*a, **k):
            raise RuntimeError("network blocked")

    monkeypatch.setattr(inst, "httpx", FakeHttpx())
    calls = {}
    def fake_run_cmd(cmd, cwd=None, timeout=900):
        calls["cmd"] = cmd
        return (True, "installed")
    monkeypatch.setattr(inst, "run_cmd", fake_run_cmd)
    info = {"installer_url": "https://fake", "installer_url_win": "https://fake-ps1",
            "bin": "hermes", "start_hint": "hermes"}
    r = inst._install_official(info)
    assert r["ok"] is True
    assert "pip" in calls["cmd"] and "hermes-agent" in calls["cmd"]


def test_run_with_progress_shows_elapsed(capsys):
    """The progress helper prints a live elapsed-time line during a long op
    and clears it after - so the wizard never looks frozen."""
    import time

    from council.agents.proc import human_duration, run_with_progress

    def slow():
        time.sleep(0.6)
        return "done"

    result = run_with_progress(slow, "testing", interval=0.2)
    assert result == "done"
    out = capsys.readouterr().out
    assert "⏳ testing" in out
    assert "elapsed" in out

    assert human_duration(45) == "45s"
    assert human_duration(130) == "2m 10s"
