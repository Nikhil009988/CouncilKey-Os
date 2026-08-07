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
    assert set(ROLE_SYSTEMS) == {"hermes", "openclaw", "codex"}
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
    assert "hermes" in r.stdout and "openclaw" in r.stdout and "codex" in r.stdout


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


def test_codex_no_docker_install():
    """Codex replaces Agent Zero: npm install, local execution, NO Docker."""
    from council.agents.installer import AGENTS

    assert AGENTS["codex"]["install"] == "npm"
    assert AGENTS["codex"]["package"] == "@openai/codex"
    # runtime note says explicitly no Docker
    assert "NO Docker" in AGENTS["codex"]["runtime"]


def test_codex_configure_openrouter_writes_config(monkeypatch, tmp_path):
    """configure(codex) writes a working config for the OpenRouter provider."""
    from council.agents.installer import configure
    from council.llm import provider as lp

    monkeypatch.setattr(lp, "active_provider", lambda: "openrouter")
    monkeypatch.setenv("CODECONFIG", str(tmp_path / "config.toml"))
    res = configure("codex")
    assert res["ok"] is True
    cfg = (tmp_path / "config.toml").read_text(encoding="utf-8")
    assert "openrouter" in cfg
    assert "https://openrouter.ai/api/v1" in cfg
    assert 'env_key = "OPENROUTER_API_KEY"' in cfg
    assert 'wire_api = "responses"' in cfg
    assert "openai/gpt-5.3-codex" in cfg


def test_codex_configure_needs_provider(monkeypatch, tmp_path):
    """No provider configured -> clear error with the exact fix command."""
    from council.agents.installer import configure
    from council.llm import provider as lp

    monkeypatch.setattr(lp, "active_provider", lambda: None)
    monkeypatch.setenv("CODECONFIG", str(tmp_path / "config.toml"))
    res = configure("codex")
    assert res["ok"] is False
    assert "councilkey setup" in res["hint"]
    # nothing written
    assert not (tmp_path / "config.toml").exists()


def test_codex_configure_anthropic_clear_error(monkeypatch, tmp_path):
    """Anthropic keys can't drive Codex - the message says so plainly."""
    from council.agents.installer import configure
    from council.llm import provider as lp

    monkeypatch.setattr(lp, "active_provider", lambda: "anthropic")
    monkeypatch.setenv("CODECONFIG", str(tmp_path / "config.toml"))
    res = configure("codex")
    assert res["ok"] is False
    assert "cannot use an Anthropic key" in res["error"]


def test_cli_key_show_and_list(tmp_path):
    """`councilkey key show NAME` prints the raw key (for launchers),
    `key list` only shows a masked hint."""
    import subprocess

    from council.secrets.vault import set_secret

    set_secret("OPENROUTER_API_KEY", "sk-or-test-1234567890")

    r = subprocess.run(
        [str(cli_path()), "key", "show", "OPENROUTER_API_KEY"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "sk-or-test-1234567890"

    r = subprocess.run([str(cli_path()), "key", "list"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert "OPENROUTER_API_KEY" in r.stdout
    assert "sk-or-test-1234567890" not in r.stdout  # masked

    r = subprocess.run([str(cli_path()), "key", "show", "NOPE_KEY"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 1
    assert "no key named" in r.stderr


def test_pendrive_run_codex_launcher():
    """The stick launcher keeps Codex state+config on the stick and loads
    the provider key from the encrypted vault at launch time."""
    sh = (ROOT / "scripts" / "pendrive-setup.sh").read_text(encoding="utf-8")
    for token in ("RUN-CODEX.bat", "run-codex.sh", "CODEX_HOME", "CODECONFIG",
                  "council-data/codex", "key show OPENROUTER_API_KEY",
                  "agents configure codex", r"tools\codex\node_modules\.bin\codex.cmd"):
        assert token in sh, token

    ps = (ROOT / "scripts" / "pendrive-setup.ps1").read_text(encoding="utf-8")
    for token in ("RUN-CODEX.bat", "CODEX_HOME", "CODECONFIG",
                  "council-data\\codex", "key show OPENROUTER_API_KEY",
                  "agents configure codex", "tools\\codex\\node_modules\\.bin\\codex.cmd"):
        assert token in ps, token


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
    assert set(clients) == {"hermes", "openclaw", "codex"}
    assert set(modes) == {"hermes", "openclaw", "codex"}


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


def test_windows_scripts_present():
    """Every user-facing task has a native Windows path."""

    for rel in (
        "scripts/pendrive-setup.ps1",
        "scripts/setup.ps1",
        "scripts/start.ps1",
        "scripts/start.bat",
        "install.ps1",
        "councilkey.bat",
    ):
        assert (ROOT / rel).exists(), rel


def test_start_bat_derives_council_home():
    """The generated START.bat derives COUNCIL_HOME from the stick drive -
    no bash-style env file parsing that would break in cmd."""
    s = (ROOT / "scripts" / "pendrive-setup.sh").read_text(encoding="utf-8")
    assert 'set "COUNCIL_HOME=%~dp0council-data"' in s
    # the old broken cmd parsing of a bash export line is gone
    assert ".pendrive.env" not in s


def test_pendrive_cli_platform_aware():
    """councilkey pendrive picks the .ps1 on Windows, .sh elsewhere."""
    import council.cli as cli

    # the dispatch code contains both branches
    src = open(cli.__file__, encoding="utf-8").read()
    assert "pendrive-setup.ps1" in src
    assert "pendrive-setup.sh" in src


def test_pendrive_script_has_portable_openclaw():
    """The pendrive build installs OpenClaw onto the stick and redirects its
    state there (so agents don't live on the host PC)."""
    s = (ROOT / "scripts" / "pendrive-setup.sh").read_text(encoding="utf-8")
    assert "npm install --prefix" in s
    assert "openclaw@latest" in s
    assert "OPENCLAW_STATE_DIR" in s
    assert "RUN-OPENCLAW.bat" in s
    assert "council-data/openclaw" in s

    ps = (ROOT / "scripts" / "pendrive-setup.ps1").read_text(encoding="utf-8")
    assert "RUN-OPENCLAW.bat" in ps
    assert "OPENCLAW_STATE_DIR" in ps


def test_dashboard_chat_ui():
    """The dashboard Council tab is a real chat UI (bubbles, stream, clear)."""
    html = (ROOT / "council" / "orchestrator" / "index.html").read_text(encoding="utf-8")
    for token in ("chat-messages", "addMsg(", "msg-council", "chat-clear", "askStream(body)"):
        assert token in html, token
    # the old plain result box is gone
    assert "council-final" not in html


def test_pendrive_installs_all_agents_onto_stick():
    """The pendrive build puts EVERY agent on the stick (no host installs)."""
    sh = (ROOT / "scripts" / "pendrive-setup.sh").read_text(encoding="utf-8")
    # pip agents into the stick venv + openclaw npm --prefix
    assert "hermes-agent crewai aider-chat" in sh
    assert "npm install --prefix" in sh
    # launchers for every agent
    for name in ("RUN-OPENCLAW", "RUN-HERMES", "RUN-CREWAI", "RUN-AIDER", "RUN-CODEX"):
        assert name in sh
    # launchers are outside the --no-agents branch (always written)
    launcher_pos = sh.find("# --- launchers")
    no_agents_pos = sh.find("--no-agents")
    assert launcher_pos > no_agents_pos
    # state on the stick
    assert "council-data/openclaw" in sh
    assert "council-data/agents" in sh

    ps = (ROOT / "scripts" / "pendrive-setup.ps1").read_text(encoding="utf-8")
    for name in ("RUN-OPENCLAW", "RUN-HERMES", "RUN-CREWAI", "RUN-AIDER", "RUN-CODEX"):
        assert name in ps


def test_dashboard_overview_tab():
    """The dashboard has an Overview/home tab with live status cards."""
    html = (ROOT / "council" / "orchestrator" / "index.html").read_text(encoding="utf-8")
    for token in ("tab-overview", "ov-provider", "ov-roles", "loadOverview", "ov-last"):
        assert token in html, token


def test_setup_scripts_have_auto_full_mode():
    """Clone -> one command must install everything (setup.sh --auto /
    setup.ps1 -Full)."""
    sh = (ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert "--auto" in sh
    assert "agents install" in sh
    assert "OPENAI_API_KEY" in sh

    ps = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8")
    assert "-Full" in ps
    assert "agents install" in ps
    assert "OPENAI_API_KEY" in ps


def test_verify_checks_external_binaries():
    """agents verify must check that installed external agent binaries run."""
    import council.cli as cli_mod

    src = open(cli_mod.__file__, encoding="utf-8").read()
    assert "external agent binaries" in src
    assert "2/2" in src
    assert "--version" in src


def test_openclaw_launcher_redirects_workspace():
    """RUN-OPENCLAW.bat / run-openclaw.sh must redirect OpenClaw's WORKSPACE
    + HOME to the stick (not just state) - verified from OpenClaw's source:
    workspace resolves from OPENCLAW_WORKSPACE_DIR."""
    sh = (ROOT / "scripts" / "pendrive-setup.sh").read_text(encoding="utf-8")
    assert "OPENCLAW_WORKSPACE_DIR" in sh
    assert "OPENCLAW_HOME" in sh
    assert "council-data/openclaw/workspace" in sh

    ps = (ROOT / "scripts" / "pendrive-setup.ps1").read_text(encoding="utf-8")
    assert "OPENCLAW_WORKSPACE_DIR" in ps
    assert "OPENCLAW_HOME" in ps


def test_cli_which_shows_install_path():
    """councilkey which must print where the CLI is installed - so users can
    verify PC vs pendrive copy."""
    import subprocess

    r = subprocess.run([str(cli_path()), "which"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert "CouncilKey-Os" in r.stdout


def test_version_shows_install_location():
    import subprocess

    r = subprocess.run([str(cli_path()), "version"], capture_output=True, text=True, timeout=60)
    assert "installed at:" in r.stdout


def test_pendrive_launchers_print_running_from():
    """Stick launchers must announce where they run from, so the user can
    tell PC copy from pendrive copy."""
    sh = (ROOT / "scripts" / "pendrive-setup.sh").read_text(encoding="utf-8")
    assert "Running from:" in sh
    assert "Running from: %~dp0" in sh          # START.bat + RUN-OPENCLAW.bat
    assert "Running from: $STICK" in sh         # run-openclaw.sh


def test_pendrive_session_mode():
    """The stick has session-mode launchers: code clones to the PC, memory
    stays on the stick, and the PC copy is wiped on end."""
    sh = (ROOT / "scripts" / "pendrive-setup.sh").read_text(encoding="utf-8")
    assert "start-session.sh" in sh
    assert "end-session.sh" in sh
    assert "START-SESSION.bat" in sh
    assert "END-SESSION.bat" in sh
    assert "server.pid" in sh          # session tracks its own process
    assert "rm -rf" in sh              # cleanup on end
    assert "council-data" in sh        # memory stays on the stick

    ps = (ROOT / "scripts" / "pendrive-setup.ps1").read_text(encoding="utf-8")
    assert "START-SESSION.bat" in ps
    assert "END-SESSION.bat" in ps


def test_pendrive_agent_menu_and_readme():
    """The stick has an agent menu (any agent or all at once) + README."""
    sh = (ROOT / "scripts" / "pendrive-setup.sh").read_text(encoding="utf-8")
    assert "AGENTS.bat" in sh
    assert "agents-menu.sh" in sh
    assert "launch-all.sh" in sh
    assert "PENDRIVE-README.txt" in sh
    assert "ALL agents + dashboard" in sh   # all-at-once option
    assert "council-data" in sh

    ps = (ROOT / "scripts" / "pendrive-setup.ps1").read_text(encoding="utf-8")
    assert "AGENTS.bat" in ps
    assert "PENDRIVE-README.txt" in ps


def test_active_provider_prefers_configured(monkeypatch, tmp_path):
    """The configured provider (from setup) must win over any stale key -
    this was the 401 bug: openai was picked because a stale key existed."""
    from council.llm import provider as pv

    summary_file = tmp_path / "setup-summary.json"
    summary_file.write_text('{"provider": "openrouter"}', encoding="utf-8")
    monkeypatch.setattr(pv, "_provider_cache", None)

    # both an openai key AND the configured openrouter key exist
    def fake_key_for(name):
        return "sk-x" if name in ("openai", "openrouter") else None
    monkeypatch.setattr(pv, "_key_for", fake_key_for)
    monkeypatch.setattr("council.agents.setup_wizard.COUNCIL_HOME", tmp_path)
    monkeypatch.setattr("council.agents.setup_wizard.summary",
                        lambda: {"provider": "openrouter"})

    assert pv.active_provider() == "openrouter"


def test_401_error_message_mentions_key(monkeypatch):
    """A 401 must tell the user their API key is wrong/expired."""
    from council.llm import provider as pv

    monkeypatch.setattr(pv, "_key_for", lambda n: "sk-x")
    monkeypatch.setattr(pv, "active_provider", lambda: "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9")  # unreachable

    import asyncio
    client = pv.ProviderAgentClient("hermes", provider="openai")
    # force the httpx call to fail with 401
    import httpx
    class FakeResp:
        status_code = 401
        def raise_for_status(self):
            raise httpx.HTTPStatusError("401 Unauthorized", request=None, response=None)
    class FakeTransport:
        async def handle_async_request(self, req):
            raise httpx.HTTPStatusError("Client error '401 Unauthorized'", request=req, response=None)
    # simpler: stub the _ask_openai_compat to raise 401
    async def boom(prompt, system, model, timeout):
        raise httpx.HTTPStatusError("Client error '401 Unauthorized' for url 'https://api.openai.com'", request=None, response=None)
    monkeypatch.setattr(client, "_ask_openai_compat", boom)
    result = asyncio.run(client.ask("hi"))
    assert "401" in result.status
    assert "wrong or expired" in result.status or "wrong or expired" in result.response


def test_pendrive_push_copies_data(tmp_path):
    """pendrive-push copies the PC's council data (keys, journal, memory)
    onto the stick so the stick works standalone."""
    from council.agents.pendrive_push import _copy_tree, pc_council_home

    src = tmp_path / "home"
    (src / "journal").mkdir(parents=True)
    (src / "journal" / "entry.md").write_text("x", encoding="utf-8")
    (src / "secrets").mkdir()
    (src / "shared").mkdir()

    dst = tmp_path / "stick" / "council-data"
    copied = _copy_tree(src, dst)
    assert set(copied) == {"journal", "secrets", "shared"}
    assert (dst / "journal" / "entry.md").exists()

    # pc_council_home respects COUNCIL_HOME
    import os
    os.environ["COUNCIL_HOME"] = str(src)
    assert pc_council_home() == src


def test_cli_has_pendrive_push():
    import council.cli as cli_mod

    src = open(cli_mod.__file__, encoding="utf-8").read()
    assert "pendrive-push" in src
    assert "pendrive_push" in src


def test_setup_scripts_check_prerequisites():
    """setup must give CLEAR errors when python/git are missing (not a
    cryptic crash)."""
    sh = (ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert "Python is not installed" in sh
    assert "git is not installed" in sh
    assert "exit 1" in sh

    ps = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8")
    assert "Python is not installed" in ps
    assert "winget install Python.Python.3.11" in ps
    assert "git is not installed" in ps


def test_start_script_picks_free_port():
    """start.sh detects a busy port and picks the next free one."""
    sh = (ROOT / "scripts" / "start.sh").read_text(encoding="utf-8")
    assert "port $PORT is busy" in sh
    assert "seq $((PORT + 1))" in sh
    assert "COUNCIL_PORT" in sh


def test_doctor_reports_provider_status():
    """doctor must tell the user whether a model provider key is set."""
    import council.cli as cli_mod

    src = open(cli_mod.__file__, encoding="utf-8").read()
    assert "model provider" in src
    assert "no API key - run: councilkey setup" in src
    assert "add a key with: councilkey setup" in src
