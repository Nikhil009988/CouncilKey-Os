"""CouncilKey-Os v1.5 - interactive setup wizard tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_wizard_providers_defined():
    from council.agents.setup_wizard import PROVIDERS

    assert set(PROVIDERS) == {"ollama", "openai", "anthropic", "gemini", "openrouter", "none"}
    assert PROVIDERS["ollama"]["choice"] == "ollama"
    assert PROVIDERS["openai"]["env"] == "OPENAI_API_KEY"
    assert PROVIDERS["openai"]["choice"] == "openai-api-key"


def test_wizard_noninteractive_runs():
    """councilkey setup --provider none --no-agents --no-llm --skip-tests
    must complete without hanging (no prompts in flag mode)."""
    import subprocess

    r = subprocess.run(
        [str(ROOT / ".venv/bin/councilkey"), "setup",
         "--provider", "none", "--no-agents", "--no-llm", "--skip-tests"],
        capture_output=True, text=True, timeout=120,
    )
    assert "Setup finished" in r.stdout
    assert r.returncode == 0, r.stdout[-400:]


def test_wizard_stores_key_in_vault(monkeypatch):
    """Choosing a cloud provider stores the key in the encrypted vault."""
    from council.agents import setup_wizard as w
    from council.secrets.vault import get_secret

    monkeypatch.setattr(w, "check_prereqs", lambda: {"python": True, "git": True})
    # patch out heavy steps so the test is fast
    monkeypatch.setattr(w, "run_wizard", lambda *a, **k: None)  # noqa

    # directly exercise the store path
    w._store_key("OPENAI_API_KEY", "sk-test-xyz")
    assert get_secret("OPENAI_API_KEY") == "sk-test-xyz"


def test_configure_openclaw_missing_binary():
    from council.agents.setup_wizard import _configure_openclaw

    # openclaw may or may not be installed; result must be a dict with ok key
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
    # either a header (no keys) or export lines - both are valid
    assert ("export " in r.stdout) or ("no API keys" in r.stdout)
