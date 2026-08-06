"""CouncilKey-Os interactive setup wizard.

Runs `councilkey setup`:

  1. prerequisite check
  2. local LLM (Ollama + model)          - the council's real brain
  3. external agents (optional)          - Hermes / OpenClaw / Agent Zero
  4. model provider + API keys           - local Ollama (free) or a cloud
                                          provider; keys are stored in the
                                          encrypted secrets vault and handed
                                          to the agents' own config
  5. tests + verify

Non-interactive mode (for automation/CI):
    councilkey setup --provider openai --api-key sk-... --no-agents --no-llm --skip-tests
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from council import __version__

ROOT = Path(__file__).resolve().parent.parent.parent
COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))

# provider -> (display name, env var name, openclaw auth-choice)
PROVIDERS: dict[str, dict[str, str]] = {
    "ollama": {"name": "Local Ollama (free, offline)", "env": "OLLAMA_API_KEY", "choice": "ollama"},
    "openai": {"name": "OpenAI", "env": "OPENAI_API_KEY", "choice": "openai-api-key"},
    "anthropic": {"name": "Anthropic", "env": "ANTHROPIC_API_KEY", "choice": "anthropic-api-key"},
    "gemini": {"name": "Google Gemini", "env": "GEMINI_API_KEY", "choice": "gemini-api-key"},
    "openrouter": {"name": "OpenRouter (many models)", "env": "OPENROUTER_API_KEY", "choice": "openrouter-api-key"},
    "none": {"name": "Skip (configure later)", "env": "", "choice": "skip"},
}

DEFAULT_MODEL = "qwen2.5:3b"


# ---------------------------------------------------------------- prompts
def _ask(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{question}{suffix}: ").strip() or default
    except EOFError:
        return default


def _confirm(question: str, default: bool = True) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        try:
            ans = input(f"{question}{suffix}: ").strip().lower()
        except EOFError:
            return default
        if ans in ("", "y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        if ans.startswith("y"):
            return True
        if ans.startswith("n"):
            return False
        # invalid input -> ask again (but in non-interactive EOF just default)
        try:
            input("  (type y or n) ")
        except EOFError:
            return default


def _secret(question: str) -> str:
    try:
        return getpass.getpass(f"{question}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


# ---------------------------------------------------------------- steps
def check_prereqs() -> dict[str, bool]:
    import shutil

    return {
        "python": sys.executable is not None,
        "git": shutil.which("git") is not None,
        "node": shutil.which("node") is not None,
        "npm": shutil.which("npm") is not None,
        "docker": shutil.which("docker") is not None,
        "ollama": shutil.which("ollama") is not None,
    }


def _banner() -> None:
    print("=" * 58)
    print(f"  CouncilKey-Os {__version__} - interactive setup")
    print("  everything local by default · no demo, real inference")
    print("=" * 58)


def _save_summary(summary: dict[str, Any]) -> None:
    try:
        COUNCIL_HOME.mkdir(parents=True, exist_ok=True)
        (COUNCIL_HOME / "setup-summary.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8"
        )
    except Exception:
        pass


def _store_key(env_name: str, value: str) -> None:
    """Store an API key in the encrypted secrets vault."""
    from council.secrets.vault import set_secret

    set_secret(env_name, value)


def _configure_openclaw(provider: str, key: str, model: str | None = None) -> dict[str, Any]:
    """Configure the installed OpenClaw CLI non-interactively."""
    import shutil
    import subprocess

    if shutil.which("openclaw") is None:
        return {"ok": False, "error": "openclaw not installed"}
    info = PROVIDERS[provider]
    cmd = ["openclaw", "onboard", "--non-interactive", "--accept-risk",
           "--auth-choice", info["choice"]]
    if provider == "ollama":
        # ollama choice probes the running local server; the provider is
        # registered via OLLAMA_API_KEY env (any value) for model selection
        pass
    elif info["choice"] == "skip":
        return {"ok": True, "detail": "provider skipped - configure later with 'openclaw onboard'"}
    else:
        flag = "--" + info["choice"].replace("_", "-")
        cmd += [flag, key]
        if model:
            cmd += ["--custom-model-id", model]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        out = (proc.stdout or "") + (proc.stderr or "")
        tail = out[-300:]
        # openclaw may exit non-zero even after a successful config (warnings
        # about missing daemon etc.) - treat a written config as success
        success = proc.returncode == 0 or ("Updated config" in out or "Auth" in out and "ok" in out.lower())
        return {"ok": success, "detail": tail[:250]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_wizard(
    provider: str | None = None,
    api_key: str | None = None,
    no_agents: bool = False,
    no_llm: bool = False,
    skip_tests: bool = False,
) -> int:
    """Run the interactive (or flag-driven) setup wizard. Returns exit code."""
    interactive = provider is None and api_key is None
    _banner()

    summary: dict[str, Any] = {
        "version": __version__,
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "steps": [],
        "provider": None,
        "keys_stored": [],
        "agents": {},
    }
    ok_all = True

    def note(step: str, ok: bool, detail: str = "") -> None:
        mark = "✅" if ok else "⚠"
        print(f"  {mark} {step}" + (f" - {detail}" if detail else ""))
        summary["steps"].append({"step": step, "ok": ok, "detail": detail})
        nonlocal ok_all
        if not ok:
            ok_all = False

    # 1. prereqs
    prereqs = check_prereqs()
    missing = [k for k, v in prereqs.items() if not v and k in ("git", "python")]
    if missing:
        note("prerequisites", False, f"missing: {', '.join(missing)} - install them first")
        print("  required: python 3.11+ and git")
        return 1
    note("prerequisites", True)

    # 2. local LLM
    if no_llm:
        note("local LLM (Ollama)", True, "skipped (--no-llm)")
    else:
        from council.llm.agents import ollama_available

        if ollama_available():
            note("local LLM (Ollama)", True, "already running")
        else:
            want = True
            if interactive:
                want = _confirm("Install Ollama + pull qwen2.5:3b (~1.9GB)?", default=True)
            if want:
                from council.cli import cmd_llm

                if cmd_llm("install", None) != 0:
                    note("install Ollama", False, "see https://ollama.com/download")
                else:
                    note("install Ollama", True)
                if cmd_llm("pull", DEFAULT_MODEL) != 0:
                    note(f"pull model {DEFAULT_MODEL}", False, "run later: councilkey llm pull")
                else:
                    note(f"pull model {DEFAULT_MODEL}", True)
            else:
                note("local LLM", True, "skipped")

    # 3. provider + API keys
    if interactive:
        print("\n  Model provider for the external agents (Hermes / OpenClaw):")
        for i, (pid, p) in enumerate(PROVIDERS.items(), 1):
            print(f"    {i}) {p['name']}")
        choice = _ask("Choose provider", default="1")
        try:
            provider = list(PROVIDERS)[int(choice) - 1]
        except (ValueError, IndexError):
            provider = "ollama"

    if provider in (None, "none"):
        note("model provider", True, "skipped - configure later")
    else:
        info = PROVIDERS[provider]
        env = info["env"]
        key = api_key
        if provider == "ollama":
            # local provider - no real key needed, any value registers it
            key = key or "local"
            _store_key(env, key)
            summary["keys_stored"].append(env)
            note("model provider", True, "Local Ollama (free, offline)")
        else:
            if interactive and not key and env:
                key = _secret(f"  {info['name']} API key")
            if env and key:
                _store_key(env, key)
                summary["keys_stored"].append(env)
                note("API key stored", True, f"{env} -> encrypted vault")
            elif env and not key:
                note("API key", False, f"{env} not provided - agents won't answer until set")
            else:
                note("model provider", True, info["name"])
        summary["provider"] = provider

        # configure OpenClaw with the provider (non-interactive)
        cfg = _configure_openclaw(provider, key or "")
        if cfg.get("ok"):
            note("configure OpenClaw", True, cfg.get("detail", "")[:80])
        else:
            note("configure OpenClaw", False, cfg.get("error", ""))

    # 4. external agents
    if no_agents:
        note("external agents", True, "skipped (--no-agents)")
    else:
        install_all = True
        if interactive:
            install_all = _confirm("Install the external agents (Hermes/OpenClaw/Agent Zero)?", default=False)
        if install_all:
            from council.agents.installer import AGENTS
            from council.agents.installer import install as agent_install

            for name in AGENTS:
                print(f"\n  == {name} ==")
                res = agent_install(name)
                summary["agents"][name] = {"ok": res.get("ok"), "detail": res.get("error") or res.get("next", "")}
                if res.get("ok"):
                    note(f"install {name}", True, res.get("next", "installed"))
                else:
                    note(f"install {name}", False, res.get("error", ""))
                    if res.get("hint"):
                        print(f"       hint: {res['hint']}")
        else:
            note("external agents", True, "skipped")

    # 5. tests
    if skip_tests:
        note("test suite", True, "skipped (--skip-tests)")
    else:
        import subprocess

        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-q"], cwd=ROOT, capture_output=True, text=True, timeout=600
        )
        tail = (r.stdout or "").strip().splitlines()[-1] if r.stdout else "?"
        note("test suite", r.returncode == 0, tail[:80])

    # 6. verify
    from council.cli import cmd_agents

    print("\n  Verifying the council (real ask)...")
    cmd_agents("verify", [])

    _save_summary(summary)
    print("\n" + "=" * 58)
    print("  Setup finished.")
    print("  Start the dashboard:   councilkey serve   ->  http://localhost:8443")
    print("  Status:                councilkey agents status / councilkey llm status")
    print("=" * 58)
    return 0 if ok_all else 1


def summary() -> dict[str, Any]:
    """Show what the last setup run configured (for /api/status etc.)."""
    p = COUNCIL_HOME / "setup-summary.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
