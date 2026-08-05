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
            check(f"optional {opt}", False, "not installed")

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
    """Manage the 3 agents: status / install / start."""
    from council.agents.installer import AGENTS, install, start, status

    selected = names or list(AGENTS)
    bad = [n for n in selected if n not in AGENTS]
    if bad:
        print(f"unknown agent(s): {', '.join(bad)} - choose from {sorted(AGENTS)}")
        return 2

    if action == "status":
        data = status(names)
        print(f"{'agent':<11}{'role':<8}{'port':<7}{'state'}")
        print("-" * 40)
        for name, info in data.items():
            mark = {"running": "🟢", "installed": "🟡", "not installed": "⚪"}.get(info["state"], "?")
            print(f"{mark} {name:<10}{info['role']:<8}{info['port']:<7}{info['state']}")
        print("-" * 40)
        missing = [n for n, i in data.items() if i["state"] == "not installed"]
        if missing:
            print("not installed:", ", ".join(missing))
            print("download them with: councilkey agents install")
        return 0

    if action == "install":
        prereqs = __import__("council.agents.installer", fromlist=["check_prereqs"]).check_prereqs()
        if not prereqs["git"]:
            print("❌ git not found - install git first")
            return 1
        if any(n in selected for n in ("openclaw",)) and not prereqs["npm"]:
            print("⚠ npm not found - OpenClaw needs Node.js/npm (its deps step will fail)")
        failed = False
        for name in selected:
            print(f"\n== Installing {name} ({AGENTS[name]['role']}) ==")
            result = install(name)
            for step in result.get("steps", []):
                mark = "✅" if step.get("ok") else "❌"
                print(f"  {mark} {step.get('step')}: {(step.get('detail') or '')[:120]}")
            if result.get("ok"):
                print(f"  -> {name} ready at {result['dir']}")
            else:
                failed = True
                print(f"  ❌ {result.get('error', 'install failed')}")
                print(f"     hint: {result.get('hint', '')}")
        print("\nAgents status:")
        cmd_agents("status", [])
        return 1 if failed else 0

    if action == "start":
        failed = False
        for name in selected:
            print(f"== starting {name} ==")
            result = start(name)
            if result.get("ok"):
                print(f"  ✅ {name} up on port {result.get('port')} (log: {result.get('log', '-')})")
            else:
                failed = True
                print(f"  ❌ {result.get('error')}")
                print(f"     hint: {result.get('hint', '')}")
        return 1 if failed else 0

    if action == "verify":
        """Real smoke test: ask every agent and show what backend answered."""
        import asyncio

        from council.orchestrator.agents import build_default_clients, client_modes

        print("== verifying the 3 agents (real ask) ==")
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
            await asyncio.gather(*[_check(n) for n in selected])

        asyncio.run(_run_all())
        print("\nlegend: gateway = external agent server | local-llm = ollama model | mock = nothing available")
        return 0

    return 2


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="councilkey", description="CouncilKey-Os control tool")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="run the dashboard + API server")
    p_serve.add_argument("--host", default=os.environ.get("COUNCIL_HOST", "0.0.0.0"))
    p_serve.add_argument("--port", type=int, default=int(os.environ.get("COUNCIL_PORT", "8443")))

    sub.add_parser("doctor", help="environment health check")

    p_storage = sub.add_parser("storage", help="storage audit/optimize")
    p_storage.add_argument("--dry-run", action="store_true", help="only report, don't delete")

    sub.add_parser("version", help="print version")

    p_agents = sub.add_parser("agents", help="manage the 3 agents (status/install/start/verify)")
    p_agents.add_argument("action", nargs="?", default="status", choices=["status", "install", "start", "verify"])
    p_agents.add_argument("names", nargs="*", help="agent names (default: all)")

    p_llm = sub.add_parser("llm", help="manage the local LLM backend (status/install/pull)")
    p_llm.add_argument("action", nargs="?", default="status", choices=["status", "install", "pull"])
    p_llm.add_argument("model", nargs="?", help="model to pull (default: qwen2.5:3b)")

    args = parser.parse_args(argv)

    if args.version:
        print(cmd_version())
        return

    if args.command == "serve":
        sys.exit(cmd_serve(args.host, args.port))
    elif args.command == "doctor":
        sys.exit(cmd_doctor())
    elif args.command == "storage":
        sys.exit(cmd_storage(args.dry_run))
    elif args.command == "agents":
        sys.exit(cmd_agents(args.action, args.names))
    elif args.command == "llm":
        sys.exit(cmd_llm(args.action, args.model))
    elif args.command == "version":
        print(cmd_version())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
