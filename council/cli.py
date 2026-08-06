"""CouncilKey-Os CLI - serve, doctor, storage, agents, version.

Commands:
  councilkey serve [--host H] [--port P]     Run the dashboard + API
  councilkey doctor                           Check environment health
  councilkey storage [--dry-run]              Audit / optimize storage
  councilkey agents [status|install|start]    Manage the 3 agents
  councilkey version                          Print version
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from council import __version__

ROOT = Path(__file__).resolve().parent.parent


def cmd_version() -> str:
    return __version__


_stale_check_cache: tuple[float, str] | None = None


def check_stale(timeout: float = 4.0) -> str:
    """Compare the installed version with the latest GitHub release.

    Returns a warning string (or "" when up to date / offline). Cached so
    it only hits the network once per process."""
    global _stale_check_cache
    import time as _t

    now = _t.monotonic()
    if _stale_check_cache and now - _stale_check_cache[0] < 300:
        return _stale_check_cache[1]
    try:
        import httpx

        r = httpx.get(
            "https://api.github.com/repos/Nikhil009988/CouncilKey-Os/releases/latest",
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code != 200:
            _stale_check_cache = (now, "")
            return ""
        latest = str(r.json().get("tag_name", "")).lstrip("v")
        current = __version__.lstrip("v")
        if latest and latest != current:
            msg = (f"  ⚠ you are on v{current} - the latest is v{latest}. "
                   "Run 'councilkey update' to get the fixes.")
            _stale_check_cache = (now, msg)
            return msg
        _stale_check_cache = (now, "")
        return ""
    except Exception:
        _stale_check_cache = (now, "")
        return ""


def cmd_doctor() -> int:
    """Check the runtime environment and print a health report."""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    check("python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0])

    for mod in ("fastapi", "uvicorn", "httpx", "pydantic"):
        try:
            __import__(mod)
            check(f"module {mod}", True)
        except Exception:
            check(f"module {mod}", False, "missing")

    for opt in ("yaml", "lancedb", "edge_tts", "whisper", "psutil"):
        try:
            __import__(opt)
            check(f"optional {opt}", True)
        except Exception:
            # optional modules are informative, not failures
            checks.append((f"optional {opt}", True, "not installed (optional - feature disabled)"))

    home = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
    writable = False
    try:
        home.mkdir(parents=True, exist_ok=True)
        probe = home / ".write-test"
        probe.write_text("ok")
        probe.unlink()
        writable = True
    except Exception:
        pass
    check(f"council home writable ({home})", writable)

    agents = {}
    try:
        from council.orchestrator.agents import build_default_clients

        async def _probe() -> dict[str, str]:
            clients = build_default_clients()
            results: dict[str, str] = {}
            for name, client in clients.items():
                try:
                    result = await client.ask("ping", timeout=2.0)
                    results[name] = result.status
                except Exception as exc:  # pragma: no cover
                    results[name] = f"error: {exc}"
            return results

        agents = asyncio.run(_probe())
    except Exception as exc:
        check("agent clients", False, str(exc))
    else:
        check("agent clients", True, json.dumps(agents))

    from council.llm.ollama import is_running

    ollama = is_running()
    check("ollama", bool(ollama.get("running")), str(ollama.get("error", "")))

    stale = check_stale()
    if stale:
        print(stale)
    print(f"CouncilKey-Os {__version__} doctor report")
    print("=" * 60)
    failed = 0
    for name, ok, detail in checks:
        mark = "✅" if ok else "❌"
        print(f"{mark} {name}" + (f" - {detail}" if detail else ""))
        if not ok:
            failed += 1
    print("=" * 60)
    print(f"{len(checks) - failed}/{len(checks)} checks passed")
    return 0 if failed == 0 else 1


def cmd_storage(dry_run: bool) -> int:
    from council.storage.optimizer import audit, optimize

    report = audit()
    print(json.dumps(report, indent=2))
    if not dry_run:
        result = optimize(dry_run=False)
        print("\nOptimize:", json.dumps(result, indent=2))
    return 0


def cmd_serve(host: str, port: int) -> int:
    import uvicorn

    os.environ.setdefault("COUNCIL_HOME", "/var/lib/council")
    from council.orchestrator.main import app

    uvicorn.run(app, host=host, port=port)
    return 0


def cmd_update() -> int:
    """Pull the latest code + reinstall the package (git pull)."""
    import subprocess

    print("== updating CouncilKey-Os ==")
    if not (ROOT / ".git").exists():
        print("  ❌ not a git checkout - re-clone instead:")
        print("     git clone https://github.com/Nikhil009988/CouncilKey-Os.git")
        return 1
    r = subprocess.run(["git", "pull", "--ff-only"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    print((r.stdout or r.stderr).strip()[-400:])
    if r.returncode != 0:
        print("  ⚠ pull failed - fix conflicts or re-clone")
        return 1
    print("  reinstalling the package...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(ROOT)],
                   cwd=ROOT, capture_output=True, text=True, timeout=300)
    print("  ✅ updated - run 'councilkey version' to confirm")
    return 0


def cmd_llm(action: str, model: str | None) -> int:
    """Manage the local LLM backend (Ollama): status / install / pull."""
    from council.llm.agents import DEFAULT_MODEL, installed_models, ollama_available
    from council.llm.ollama import pull as ollama_pull

    if action == "status":
        up = ollama_available()
        print(f"ollama:      {'🟢 running' if up else '🔴 not running'}")
        print(f"base url:    {os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')}")
        models = installed_models()
        if models:
            print(f"models:      {', '.join(models)}")
        else:
            print("models:      none installed")
        print(f"recommended: {DEFAULT_MODEL} (pull with: councilkey llm pull)")
        if not up:
            print("\nhint: install ollama first -> councilkey llm install")
        return 0 if up else 1

    if action == "install":
        print("Installing Ollama (local LLM server)...")
        if sys.platform == "win32":
            print("  Windows: run this in PowerShell (admin):")
            print("    winget install --id Ollama.Ollama -e")
            print("  then start it: ollama serve  (or the Ollama app)")
        else:
            print("  downloading the official installer...")
            import subprocess as sp

            r = sp.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh"],
                capture_output=True,
                text=True,
            )
            if r.returncode != 0:
                print("  ❌ could not reach ollama.com from this machine.")
                print("     install manually from https://ollama.com/download")
                return 1
            r2 = sp.run(["sh"], input=r.stdout, capture_output=True, text=True)
            print(r2.stdout[-400:] or r2.stderr[-400:])
            if r2.returncode != 0:
                print("  ❌ ollama install failed - install manually from https://ollama.com/download")
                return 1
        print("\nnext:  councilkey llm pull   (downloads a model, ~2GB)")
        return 0

    if action == "pull":
        target = model or DEFAULT_MODEL
        print(f"Pulling model {target!r} (can take a few minutes)...")
        if not ollama_available():
            print("  ❌ ollama is not running - install & start it first (councilkey llm install)")
            return 1
        result = ollama_pull(target)
        if result.get("ok"):
            print(f"  ✅ {target} ready")
            return 0
        print(f"  ❌ pull failed: {result.get('error', 'unknown error')}")
        return 1
    return 2


def cmd_agents(action: str, names: list[str]) -> int:
    """Manage the 3 external agents: status / install / start / verify.

    The external agents (Hermes, OpenClaw, Agent Zero) are optional add-ons
    installed with their own official installers. The council itself always
    works via the local-LLM role agents (councilkey llm status/pull).
    """
    from council.agents.installer import AGENTS, install, start, status

    selected = names or list(AGENTS)
    bad = [n for n in selected if n not in AGENTS]
    if bad:
        print(f"unknown agent(s): {', '.join(bad)} - choose from {sorted(AGENTS)}")
        return 2

    if action == "status":
        data = status(names)
        print(f"{'agent':<12}{'state':<16}{'install':<24}{'runtime'}")
        print("-" * 66)
        for name, info in data.items():
            mark = "🟡" if info["state"] == "installed" else "⚪"
            print(f"{mark} {name:<11}{info['state']:<16}{info['install']:<24}{info['runtime']}")
        print("-" * 66)
        missing = [n for n, i in data.items() if i["state"] == "not installed"]
        if missing:
            print("not installed:", ", ".join(missing))
            print("install with: councilkey agents install")
        print("\nnote: all 5 external agents install standalone (agent-zero: python venv,")
        print("Docker only adds its optional terminal/browser tools).")
        print("the council itself always answers via your model provider:")
        print("      councilkey setup   /   councilkey agents env")
        return 0

    if action == "install":
        failed = False
        for name in selected:
            print(f"\n== Installing {name} ==")
            result = install(name)
            if result.get("ok"):
                for step in result.get("steps", []):
                    mark = "✅" if step.get("ok") else "❌"
                    print(f"  {mark} {step.get('step')}: {(step.get('detail') or '')[:120]}")
                if result.get("already_installed"):
                    print(f"  -> {name} is already installed")
                if result.get("next"):
                    print(f"  next: {result['next']}")
            else:
                failed = True
                print(f"  ❌ {result.get('error', 'install failed')}")
                if result.get("hint"):
                    print(f"     hint: {result['hint']}")
        print("\nAgents status:")
        cmd_agents("status", [])
        return 1 if failed else 0

    if action == "start":
        failed = False
        for name in selected:
            print(f"== starting {name} ==")
            result = start(name)
            if result.get("ok"):
                if result.get("interactive"):
                    print(f"  ✅ {name} is installed and starts. It's an interactive agent - run it yourself:")
                    print(f"     {result.get('hint', '')}")
                    if result.get("first_run"):
                        print(f"  first run: {result['first_run']}")
                    if result.get("diagnose"):
                        print(f"  health check: {result['diagnose']}")
                    if result.get("one_shot"):
                        print(f"  quick test (one-shot): {result['one_shot']}")
                else:
                    print(f"  ✅ {name}: {result.get('detail', 'ok')}")
            else:
                failed = True
                print(f"  ❌ {result.get('error')}")
                if result.get("hint"):
                    print(f"     hint: {result['hint']}")
        return 1 if failed else 0

    if action == "env":
        """Export the API keys stored in the vault for the external agents.

        Usage:  eval "$(councilkey agents env)"        (bash/zsh)
                councilkey agents env | Invoke-Expression   (PowerShell)
        """
        from council.secrets.vault import get_secret, list_secrets

        keys = [k for k in list_secrets().get("keys", []) if k.endswith("_API_KEY") or k.endswith("_KEY")]
        if not keys:
            print("# no API keys stored yet - run: councilkey setup")
            return 0
        for k in sorted(keys):
            v = get_secret(k) or ""
            if os.name == "nt":
                print(f'$env:{k} = "{v}"')
            else:
                print(f'export {k}="{v}"')
        return 0

    if action == "verify":
        """Real smoke test: ask the 3 COUNCIL ROLE agents (hermes/openclaw/
        agent-zero) and show which backend answers. crewai/aider are external
        CLIs, not council roles - they are checked by 'agents status'."""
        import asyncio

        from council.orchestrator.agents import build_default_clients, client_modes

        roles = ["hermes", "openclaw", "agent-zero"]
        print("== verifying the council (real ask - each agent up to 30s, please wait) ==")
        modes = client_modes()
        clients = build_default_clients()

        async def _check(name: str):
            try:
                r = await clients[name].ask("Reply with: OK", timeout=30.0)
                head = " ".join(r.response.split())[:60]
                print(f"  {name:<11} mode={modes[name]['mode']:<10} status={r.status:<40} reply={head!r}")
            except Exception as exc:
                print(f"  {name:<11} ERROR: {exc}")

        async def _run_all() -> None:
            await asyncio.gather(*[_check(n) for n in roles])

        asyncio.run(_run_all())
        print("\nlegend: gateway = external agent server | provider = model API (councilkey setup) | mock = nothing configured")
        print("note: crewai/aider are external CLIs - check them with: councilkey agents status")
        return 0

    return 2


def cmd_ask(
    prompt: str,
    strategy: str = "majority",
    mode: str = "together",
    agent: str | None = None,
    decompose: bool = False,
    debate: bool = False,
    rounds: int = 3,
) -> int:
    """Ask the council - ALL THREE agents at once, then the vote.

    Examples:
      councilkey ask "plan a trip"                 # 3 agents + vote (together)
      councilkey ask "..." --strategy weighted     # weighted voting
      councilkey ask "..." --alone hermes          # single agent
      councilkey ask "..." --decompose             # split into subtasks
      councilkey ask "..." --debate --rounds 3     # iterative debate
    """
    import asyncio

    from council.orchestrator.main import AskRequest, ask_council

    if decompose:
        from council.orchestrator.decomposer import run_decomposed

        print("== Council: decomposed into subtasks (all 3 agents) ==")
        result = asyncio.run(run_decomposed(prompt, strategy, 2))
    elif debate:
        from council.orchestrator.debate import run_debate

        print(f"== Council: debate ({rounds} rounds, all 3 agents) ==")
        result = asyncio.run(run_debate(prompt, rounds=rounds, strategy=strategy, min_agreement=2))
    else:
        label = f"alone ({agent})" if mode == "alone" else f"together ({strategy})"
        print(f"== Council: {label} ==")
        req = AskRequest(prompt=prompt, strategy=strategy, min_agreement=2, mode=mode, agent=agent)
        result = asyncio.run(ask_council(req))

    # votes summary
    votes = result.get("votes", {})
    approve = sum(1 for v in votes.values() if v == "approve")
    total = len(votes)
    consensus = result.get("consensus_reached", False)
    mark = "✅" if consensus else "❌"
    print(f"   votes: {', '.join(f'{a}:{v}' for a, v in votes.items())}")
    for r in result.get("responses", []):
        print(f"   - {r['agent']:<11} {r['status']:<30} {r['latency']:.1f}s")
    if mode == "alone":
        print(f"   single agent answer: {agent}")
    else:
        print(f"   consensus: {mark} {approve}/{total}")
    print()
    print(result.get("final", ""))
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="councilkey", description="CouncilKey-Os control tool")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="run the dashboard + API server")
    p_serve.add_argument("--host", default=os.environ.get("COUNCIL_HOST", "0.0.0.0"))
    p_serve.add_argument("--port", type=int, default=int(os.environ.get("COUNCIL_PORT", "8443")))

    sub.add_parser("doctor", help="environment health check")
    sub.add_parser("update", help="pull the latest code + reinstall (git pull)")

    p_storage = sub.add_parser("storage", help="storage audit/optimize")
    p_storage.add_argument("--dry-run", action="store_true", help="only report, don't delete")

    sub.add_parser("version", help="print version")

    p_agents = sub.add_parser("agents", help="manage the 3 agents (status/install/start/env/verify)")
    p_agents.add_argument("action", nargs="?", default="status",
                          choices=["status", "install", "start", "env", "verify"])
    p_agents.add_argument("names", nargs="*", help="agent names (default: all)")

    p_llm = sub.add_parser("llm", help="manage the local LLM backend (status/install/pull)")
    p_llm.add_argument("action", nargs="?", default="status", choices=["status", "install", "pull"])
    p_llm.add_argument("model", nargs="?", help="model to pull (default: qwen2.5:3b)")

    p_ask = sub.add_parser("ask", help="ask the council - ALL 3 agents at once + vote")
    p_ask.add_argument("prompt", help="the question to ask")
    p_ask.add_argument("--strategy", default="majority", choices=["majority", "weighted", "llm_judge", "hermes_decides"])
    p_ask.add_argument("--alone", metavar="AGENT", help="ask a single agent (hermes/openclaw/agent-zero)")
    p_ask.add_argument("--decompose", action="store_true", help="split into role-based subtasks")
    p_ask.add_argument("--debate", action="store_true", help="iterative multi-round debate")
    p_ask.add_argument("--rounds", type=int, default=3, help="debate rounds (default 3)")

    p_pendrive = sub.add_parser("pendrive", help="one-command setup of everything onto a USB stick")
    p_pendrive.add_argument("path", help="mount point of the pendrive (e.g. /media/USB)")
    p_pendrive.add_argument("--wizard", action="store_true", help="also run the API-key wizard into the stick")

    p_setup = sub.add_parser("setup", help="interactive setup wizard (provider, API keys, agents)")
    p_setup.add_argument("--provider", choices=["openai", "anthropic", "gemini", "openrouter", "none"],
                         help="model provider for the council + external agents")
    p_setup.add_argument("--api-key", help="API key for the provider (stored encrypted)")
    p_setup.add_argument("--no-agents", action="store_true", help="skip external agent installs")
    p_setup.add_argument("--skip-tests", action="store_true", help="don't run pytest at the end")

    args = parser.parse_args(argv)

    if args.version:
        print(cmd_version())
        return

    if args.command == "serve":
        sys.exit(cmd_serve(args.host, args.port))
    elif args.command == "ask":
        sys.exit(cmd_ask(
            prompt=args.prompt,
            strategy=args.strategy,
            mode="alone" if args.alone else "together",
            agent=args.alone,
            decompose=args.decompose,
            debate=args.debate,
            rounds=args.rounds,
        ))
    elif args.command == "doctor":
        sys.exit(cmd_doctor())
    elif args.command == "update":
        sys.exit(cmd_update())
    elif args.command == "storage":
        sys.exit(cmd_storage(args.dry_run))
    elif args.command == "agents":
        sys.exit(cmd_agents(args.action, args.names))
    elif args.command == "llm":
        sys.exit(cmd_llm(args.action, args.model))
    elif args.command == "pendrive":
        import subprocess

        # Windows users get the PowerShell builder; unix gets bash
        if os.name == "nt":
            script = ROOT / "scripts" / "pendrive-setup.ps1"
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Path", args.path]
            if args.wizard:
                cmd.append("-Wizard")
        else:
            script = ROOT / "scripts" / "pendrive-setup.sh"
            cmd = [str(script), args.path]
            if args.wizard:
                cmd.append("--wizard")
        sys.exit(subprocess.call(cmd))
    elif args.command == "setup":
        from council.agents.setup_wizard import run_wizard

        sys.exit(run_wizard(
            provider=args.provider,
            api_key=args.api_key,
            no_agents=args.no_agents,
            skip_tests=args.skip_tests,
        ))
    elif args.command == "version":
        print(cmd_version())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
