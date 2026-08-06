"""CouncilKey-Os interactive setup wizard.

Runs `councilkey setup`:

  1. prerequisite check
  2. model provider + API key      - OpenAI / OpenRouter / Gemini / Anthropic
                                     or skip; the key is stored encrypted in
                                     the secrets vault and used by the three
                                     council roles AND the external agents
  3. external agents (optional)    - Hermes / OpenClaw / Agent Zero via their
                                     official installers; OpenClaw is
                                     configured non-interactively with the
                                     chosen provider
  4. tests + verify

Non-interactive mode (automation/CI):
    councilkey setup --provider openai --api-key sk-... --no-agents --skip-tests

(Local LLM / Ollama support stays available via `councilkey llm` and is not
part of the default flow.)
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
from council.agents.proc import run_cmd

ROOT = Path(__file__).resolve().parent.parent.parent
COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))

# provider -> (display name, env var name, openclaw auth-choice)
PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {"name": "OpenAI", "env": "OPENAI_API_KEY", "choice": "openai-api-key"},
    "anthropic": {"name": "Anthropic", "env": "ANTHROPIC_API_KEY", "choice": "anthropic-api-key"},
    "gemini": {"name": "Google Gemini", "env": "GEMINI_API_KEY", "choice": "gemini-api-key"},
    "openrouter": {"name": "OpenRouter (many models)", "env": "OPENROUTER_API_KEY", "choice": "openrouter-api-key"},
    "none": {"name": "Skip (configure later)", "env": "", "choice": "skip"},
}


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
        if ans == "":
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        if ans.startswith("y"):
            return True
        if ans.startswith("n"):
            return False
        print("  (type y or n)")


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
    }


def _banner() -> None:
    print("=" * 58)
    print(f"  CouncilKey-Os {__version__} - interactive setup")
    print("  model provider + API keys · 3 agents · real answers")
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


def _configure_openclaw(provider: str, key: str) -> dict[str, Any]:
    """Configure the installed OpenClaw CLI non-interactively with the provider."""
    import shutil

    if shutil.which("openclaw") is None:
        return {"ok": False, "error": "openclaw not installed"}
    info = PROVIDERS[provider]
    cmd = ["openclaw", "onboard", "--non-interactive", "--accept-risk",
           "--auth-choice", info["choice"]]
    if info["choice"] != "skip":
        flag = "--" + info["choice"].replace("_", "-")
        cmd += [flag, key]
    ok, out = run_cmd(cmd, cwd=Path.home(), timeout=600)
    success = ok or ("Updated config" in out or "Auth" in out and "ok" in out.lower())
    return {"ok": success, "detail": out[-250:]}


def run_wizard(
    provider: str | None = None,
    api_key: str | None = None,
    no_agents: bool = False,
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

    # 2. provider + API key
    if interactive:
        print("\n  Model provider (used by the 3 council agents AND the external agents):")
        for i, (pid, p) in enumerate(PROVIDERS.items(), 1):
            print(f"    {i}) {p['name']}")
        choice = _ask("Choose provider", default="1")
        try:
            provider = list(PROVIDERS)[int(choice) - 1]
        except (ValueError, IndexError):
            provider = "openai"

    if provider in (None, "none"):
        note("model provider", True, "skipped - configure later (councilkey setup)")
        summary["provider"] = "none"
    else:
        info = PROVIDERS[provider]
        env = info["env"]
        key = api_key
        if interactive and not key:
            key = _secret(f"  {info['name']} API key")
        if not key:
            note("API key", False, f"{env} not provided - the agents won't answer until set")
            summary["provider"] = provider
        else:
            _store_key(env, key)
            summary["keys_stored"].append(env)
            summary["provider"] = provider
            note("API key stored", True, f"{env} -> encrypted vault")
            # configure OpenClaw with the provider (non-interactive)
            print("  configuring OpenClaw with your provider (can take a minute, please wait)...")
            cfg = _configure_openclaw(provider, key)
            if cfg.get("ok"):
                note("configure OpenClaw", True, cfg.get("detail", "")[:80])
            else:
                note("configure OpenClaw", False, cfg.get("error", ""))
        if info["choice"] != "skip":
            note("council role agents", True, f"will answer via {info['name']}")

    # 3. external agents
    if no_agents:
        note("external agents", True, "skipped (--no-agents)")
    else:
        install_all = False
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

    # 4. tests
    if skip_tests:
        note("test suite", True, "skipped (--skip-tests)")
    else:
        run_tests = True
        if interactive:
            run_tests = _confirm("Run the test suite now? (~1 min; you can run 'make test' later)", default=False)
        if not run_tests:
            note("test suite", True, "skipped (run 'make test' anytime)")
        else:
            t0 = time.monotonic()
            print("  running the test suite - this can take a minute or two, please wait...")
            ok, out = run_cmd([sys.executable, "-m", "pytest", "tests", "-q"], cwd=ROOT, timeout=900)
            tail = out.strip().splitlines()[-1] if out.strip() else "?"
            note("test suite", ok, f"{tail[:60]} ({int(time.monotonic() - t0)}s)")

    # 5. verify
    from council.cli import cmd_agents

    t0 = time.monotonic()
    print("\n  Verifying the council - asking each agent (real API calls, can take up to a minute)...")
    cmd_agents("verify", [])
    print(f"  verify finished in {int(time.monotonic() - t0)}s")

    _save_summary(summary)
    print("\n" + "=" * 58)
    print("  Setup finished.")
    print("  Start the dashboard:   councilkey serve   ->  http://localhost:8443")
    print("  Status:                councilkey agents status")
    print("  Keys:                  councilkey agents env")
    print("=" * 58)
    return 0 if ok_all else 1


def summary() -> dict[str, Any]:
    """Show what the last setup run configured (for the dashboard)."""
    p = COUNCIL_HOME / "setup-summary.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
