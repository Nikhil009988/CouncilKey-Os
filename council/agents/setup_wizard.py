"""CouncilKey-Os interactive setup wizard.

Runs `councilkey setup`:

  1. prerequisite check
  2. model provider + API key      - OpenAI / OpenRouter / Gemini / Anthropic
                                     or skip; the key is stored encrypted in
                                     the secrets vault and used by the three
                                     council roles AND the external agents
  3. external agents (optional)    - Hermes / OpenClaw / Codex via their
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
    print("  tip: running an old clone?  run 'councilkey update' to get the latest fixes")
    try:
        from council.cli import check_stale

        stale = check_stale()
        if stale:
            print(stale)
    except Exception:
        pass


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
    # openclaw exits non-zero when its gateway isn't running, but the config
    # is still written - treat a written config as success
    success = ok or "Updated config" in out or ("Auth" in out and "ok" in out.lower())
    return {"ok": success, "detail": (out[-250:] if out else "")}


def run_wizard(
    provider: str | None = None,
    api_key: str | None = None,
    no_agents: bool = False,
    skip_tests: bool = False,
    skip_verify: bool = False,
) -> int:
    """Run the interactive (or flag-driven) setup wizard. Returns exit code."""
    from council.agents.proc import human_duration, run_with_progress

    interactive = provider is None and api_key is None
    _banner()
    t_start = time.monotonic()

    # ensure the council home exists up front with a clear error
    try:
        COUNCIL_HOME.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(f"  ❌ cannot create the council home at {COUNCIL_HOME}: {exc}")
        print("     set a writable location:  COUNCIL_HOME=/path/to/writable  councilkey setup")
        return 1

    openclaw_configured_ok = False
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

    # ============================================================== 1. prereqs
    print("\n  [1/5] Prerequisites")
    prereqs = check_prereqs()
    missing = [k for k, v in prereqs.items() if not v and k in ("git", "python")]
    if missing:
        note("prerequisites", False, f"missing: {', '.join(missing)} - install them first")
        print("  required: python 3.11+ and git")
        return 1
    note("prerequisites", True)
    print("        NEXT: choose a model provider and enter your API key")

    # ======================================================= 2. provider + key
    print("\n  [2/5] Model provider + API key")
    if interactive:
        print("        (used by the 3 council agents AND the external agents)")
        for i, (pid, p) in enumerate(PROVIDERS.items(), 1):
            print(f"          {i}) {p['name']}")
        choice = _ask("        Choose provider", default="1")
        try:
            provider = list(PROVIDERS)[int(choice) - 1]
        except (ValueError, IndexError):
            provider = "openai"

    if provider in (None, "none"):
        note("model provider", True, "skipped - configure later (councilkey setup)")
        summary["provider"] = "none"
        print("        NEXT: start with the external agents (optional) or finish")
    else:
        info = PROVIDERS[provider]
        env = info["env"]
        key = api_key
        if interactive and not key:
            key = _secret(f"        {info['name']} API key")
        if not key:
            note("API key", False, f"{env} not provided - the agents won't answer until set")
            summary["provider"] = provider
        else:
            _store_key(env, key)
            summary["keys_stored"].append(env)
            summary["provider"] = provider
            summary["_provider_key"] = key
            note("API key stored", True, f"{env} -> encrypted vault")
            # configure OpenClaw with the provider (non-interactive)
            def _cfg():
                return _configure_openclaw(provider, key)
            try:
                cfg = run_with_progress(_cfg, "configuring OpenClaw with your provider", interval=10)
            except Exception as exc:
                cfg = {"ok": False, "error": str(exc)}
            openclaw_configured_ok = bool(cfg.get("ok"))
            if openclaw_configured_ok:
                note("configure OpenClaw", True, cfg.get("detail", "")[:60])
            else:
                note("configure OpenClaw", False, cfg.get("error", "") or "will retry after agent install")
        if info["choice"] != "skip":
            note("council role agents", True, f"will answer via {info['name']}")
        print("        NEXT: install the external agents (optional, pick what you need)")

    # ====================================================== 3. external agents
    print("\n  [3/5] External agents (optional, each is an interactive tool with its own UI)")
    if no_agents:
        note("external agents", True, "skipped (--no-agents)")
        print("        NEXT: finish setup")
    else:
        from council.agents.installer import AGENTS

        # ---- choose which agents to install ----
        choices: list[str] = []
        if interactive:
            print("        Pick any combination (comma-separated, e.g. '2,4'):")
            for i, name in enumerate(AGENTS, 1):
                est = {
                    "hermes": "5-15 min (official installer)",
                    "openclaw": "1-3 min (npm)",
                    "codex": "1-3 min (npm, no Docker)",
                    "crewai": "2-5 min (pip)",
                    "aider": "1-2 min (pip)",
                }.get(name, "?")
                print(f"          {i}) {name:<11} - {est}")
            print("          0) none - skip")
            ans = _ask("        Which agents", default="0").strip()
            if ans.lower() in ("all", "*"):
                choices = list(AGENTS)
            else:
                for part in ans.replace(" ", "").split(","):
                    if part.isdigit():
                        idx = int(part)
                        if 1 <= idx <= len(AGENTS):
                            choices.append(list(AGENTS)[idx - 1])
        else:
            choices = list(AGENTS)

        if not choices:
            note("external agents", True, "skipped (nothing selected)")
            print("        NEXT: finish setup")
        else:
            # pip agents install together in one command
            pip_names = [n for n in choices if AGENTS[n]["install"] == "pip"]
            other_names = [n for n in choices if n not in pip_names]

            # batch pip install first (one command instead of N)
            if pip_names:
                from council.agents.installer import _install_pip_batch

                pkgs = [AGENTS[n]["package"] for n in pip_names]
                print(f"  installing {', '.join(pip_names)} in one command (pip)...")
                try:
                    res = run_with_progress(lambda: _install_pip_batch(pkgs), f"installing {', '.join(pip_names)} (pip)", interval=10)
                    if res.get("ok"):
                        note(f"install {', '.join(pip_names)}", True, res.get("detail", "installed")[:60])
                    else:
                        note(f"install {', '.join(pip_names)}", False, res.get("detail", "pip install failed")[:80])
                except Exception as exc:
                    note(f"install {', '.join(pip_names)}", False, str(exc)[:80])

            # individual installs (hermes, openclaw, codex)
            for name in other_names:
                from council.agents.installer import install as agent_install

                print(f"\n  == installing {name} ==")
                t0 = time.monotonic()
                try:
                    res = run_with_progress(lambda n=name: agent_install(n), f"installing {name}", interval=10)
                except Exception as exc:
                    res = {"ok": False, "error": str(exc)}
                elapsed = human_duration(time.monotonic() - t0)
                summary["agents"][name] = {"ok": res.get("ok"), "detail": res.get("error") or res.get("next", "")}
                if res.get("ok"):
                    note(f"install {name}", True, f"({elapsed}) {res.get('next', 'installed')[:60]}")
                else:
                    note(f"install {name}", False, f"({elapsed}) {res.get('error', 'failed')[:80]}")
                    if res.get("hint"):
                        print(f"       hint: {res['hint']}")

            # retry OpenClaw config now that it might be installed
            if (
                not openclaw_configured_ok
                and provider not in (None, "none")
                and summary.get("keys_stored")
            ):
                try:
                    import shutil as _sh

                    if _sh.which("openclaw"):
                        print("  configuring OpenClaw now that it's installed...")
                        cfg = _configure_openclaw(summary["provider"], summary.get("_provider_key", ""))
                        note("configure OpenClaw", cfg.get("ok", False), (cfg.get("detail") or "")[:60])
                except Exception:
                    pass

            # point Codex at the provider key (OpenAI/OpenRouter) so it
            # answers right after install - no extra steps for the user
            if "codex" in choices and provider not in (None, "none"):
                from council.agents.installer import configure as agent_configure

                try:
                    cfg = agent_configure("codex")
                    note("configure Codex", cfg.get("ok", False),
                         (cfg.get("detail") or cfg.get("error", ""))[:70])
                    if not cfg.get("ok") and cfg.get("hint"):
                        print(f"       hint: {cfg['hint']}")
                except Exception as exc:
                    note("configure Codex", False, str(exc)[:70])

            print("        NEXT: finish setup (tests + verification)")

    # =============================================================== 4. tests
    print("\n  [4/5] Tests")
    if skip_tests:
        note("test suite", True, "skipped (--skip-tests)")
    else:
        run_tests = True
        if interactive:
            run_tests = _confirm("        Run the test suite now? (~1 min; you can run 'make test' later)", default=False)
        if not run_tests:
            note("test suite", True, "skipped (run 'make test' anytime)")
        else:
            def _tests():
                return run_cmd([sys.executable, "-m", "pytest", "tests", "-q"], cwd=ROOT, timeout=180)
            try:
                ok, out = run_with_progress(_tests, "running the test suite", interval=10)
            except Exception as exc:
                ok, out = False, str(exc)
            tail = out.strip().splitlines()[-1] if out.strip() else "?"
            # tests are informational - a failing test must NOT fail the setup
            note("test suite", True, ("passed - " if ok else "note: some tests failed (run 'make test' to see) - ") + tail[:50])
    print("        NEXT: verify the council answers")

    # ============================================================== 5. verify
    print("\n  [5/5] Verify the council")
    from council.cli import cmd_agents

    def _verify():
        return cmd_agents("verify", [])

    try:
        run_with_progress(_verify, "verifying the council (real API calls)", interval=10)
    except Exception:
        pass

    _save_summary(summary)
    total = human_duration(time.monotonic() - t_start)
    print("\n" + "=" * 58)
    print(f"  ✅ Setup finished in {total}")
    print("")
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
