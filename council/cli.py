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
from typing import Any

from council import __version__

ROOT = Path(__file__).resolve().parent.parent


def cmd_version() -> str:
    return __version__


def cmd_which() -> str:
    """Show WHERE this CLI is installed (PC vs pendrive)."""
    # stick layout: <drive>:\CouncilKey-Os + <drive>:\council-data
    on_stick = (ROOT.parent / "council-data").is_dir() or os.environ.get("COUNCIL_PENDRIVE") == "1"
    home = os.environ.get("COUNCIL_HOME", "")
    lines = [f"CouncilKey-Os {__version__}"]
    lines.append(f"installed at: {ROOT}")
    if on_stick:
        lines.append("mode         : 📦 PENDRIVE - running from the stick")
        lines.append(f"data lives on: {home or str(ROOT.parent / 'council-data')}  (unplug -> nothing stays on this PC)")
    else:
        lines.append("mode         : 💻 PC copy (the builder)")
        lines.append("  this copy BUILDS the pendrive and is where you develop.")
        lines.append("  to run from the pendrive instead:")
        lines.append("    1. build the stick:  .\\scripts\\pendrive-setup.ps1 -Path E:\\ -Wizard")
        lines.append("    2. run from it:      E:\\CouncilKey-Os\\councilkey.bat  (or double-click E:\\START.bat)")
        lines.append("    3. verify:           E:\\CouncilKey-Os\\councilkey.bat which   -> should say PENDRIVE")
    if home:
        lines.append(f"COUNCIL_HOME : {home}")
    return "\n".join(lines)


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
        # mock = no key yet (informational, not a failure)
        if any("mock" in v for v in agents.values()):
            checks.append(("agent clients", True, json.dumps(agents) + " (add a key with: councilkey setup)"))
        else:
            check("agent clients", True, json.dumps(agents))

    from council.llm.ollama import is_running
    from council.llm.provider import provider_status

    # provider status (the important one for users)
    prov = provider_status()
    active = prov.get("active")
    if active:
        cfg = prov.get("providers", {}).get(active, {})
        check("model provider", True, f"{cfg.get('name', active)} ({cfg.get('model', '')})")
    else:
        check("model provider", False, "no API key - run: councilkey setup")

    ollama = is_running()
    if ollama.get("running"):
        check("ollama", True, "running (optional)")
    else:
        checks.append(("ollama", True, "not installed (optional - not needed)"))

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


def cmd_serve(host: str, port: int, open_browser: bool = False) -> int:
    import uvicorn

    os.environ.setdefault("COUNCIL_HOME", "/var/lib/council")
    from council.orchestrator.main import app

    if open_browser:
        import threading
        import webbrowser

        url = f"http://localhost:{port}"
        print(f"  opening your browser at {url} ...")
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port)
    return 0
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
    """Manage the 3 external agents: status / install / start / env / configure / verify.

    The external agents (Hermes, OpenClaw, OpenCode) are optional add-ons
    installed with their own official installers. The council itself always
    answers via your model provider (councilkey setup).
    """
    from council.agents.installer import AGENTS, install, start, status

    selected = names or list(AGENTS)
    bad = [n for n in selected if n not in AGENTS]
    if bad:
        print(f"unknown agent(s): {', '.join(bad)} - choose from {sorted(AGENTS)}")
        return 2

    if action == "configure":
        # point an installed agent at the user's provider key (opencode today)
        from council.agents.installer import configure

        failed = False
        for name in selected:
            res = configure(name)
            if res.get("ok"):
                print(f"  ✅ {name}: {res.get('detail', 'configured')}")
                if res.get("next"):
                    print(f"     next: {res['next']}")
            else:
                failed = True
                print(f"  ❌ {name}: {res.get('error', 'configure failed')}")
                if res.get("hint"):
                    print(f"     hint: {res['hint']}")
        return 1 if failed else 0

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
        print("\nwhere the data lives:")
        for name, info in data.items():
            stick = "  ✔ on the pendrive" if info.get("on_stick") else ""
            print(f"  {name:<10} -> {info.get('data', '?')}{stick}")
        print("  (launched from the stick's RUN-*.bat, agents keep their state")
        print("   on the pendrive - nothing stays on this PC)")
        print("\nnote: all 5 external agents install standalone (opencode: npm, local, NO Docker -")
        print("it runs terminal/file/web tools directly on your PC).")
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
        """Real smoke test: ask the 3 COUNCIL ROLE agents AND check that every
        installed external agent binary actually runs."""
        import asyncio
        import shutil

        from council.orchestrator.agents import build_default_clients, client_modes

        # 1. council roles (real ask)
        roles = ["hermes", "openclaw", "opencode"]
        print("== 1/2 verifying the council (real ask - each agent up to 30s, please wait) ==")
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

        # 2. external agent binaries (installed? do they run?)
        print("\n== 2/2 external agent binaries ==")
        from council.agents.installer import AGENTS

        for name, info in AGENTS.items():

            binary = shutil.which(info["bin"])
            # venv-installed agents (crewai/aider/hermes) live in .venv
            if not binary:
                venv_bin = ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / info["bin"]
                if venv_bin.exists():
                    binary = str(venv_bin)
            if not binary:
                print(f"  {name:<11} ⚪ not installed (run: councilkey agents install {name})")
                continue
            try:
                import subprocess

                r = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30)
                out = (r.stdout or r.stderr or "").strip().splitlines()
                ver = out[0][:60] if out else "ok"
                print(f"  {name:<11} ✅ runs - {ver}")
            except Exception as exc:
                print(f"  {name:<11} ⚠ installed but failed to run: {exc}")

        print("\nlegend: gateway = external agent server | provider = model API (councilkey setup) | mock = nothing configured")
        return 0

    return 2


def cmd_key(action: str, names: list[str]) -> int:
    """Show/list API keys from the encrypted vault.

    `councilkey key show NAME` prints the raw key on stdout - used by the
    pendrive launchers (RUN-OPENCODE.bat) so agents get the SAME key as the
    council without ever storing it in plain text.
    """
    from council.secrets.vault import get_secret, list_secrets

    if action == "list":
        keys = list_secrets().get("keys", [])
        if not keys:
            print("(no keys stored yet - run: councilkey setup)")
            return 0
        for k in sorted(keys):
            v = get_secret(k) or ""
            hint = f"{v[:2]}****{v[-2:]}" if len(v) > 4 else "****"
            print(f"  {k:<28} {hint}")
        return 0

    # action == "show"
    name = names[0] if names else ""
    if not name:
        print("usage: councilkey key show <NAME>   (e.g. OPENROUTER_API_KEY)", file=sys.stderr)
        return 2
    value = get_secret(name)
    if value is None:
        print(f"no key named {name!r} in the vault - run: councilkey setup", file=sys.stderr)
        return 1
    print(value)
    return 0


def cmd_ask(
    prompt: str,
    strategy: str = "majority",
    mode: str = "together",
    agent: str | None = None,
    decompose: bool = False,
    debate: bool = False,
    rounds: int = 3,
    voice: str | None = None,
) -> int:
    """Ask the council - ALL THREE agents at once, then the vote.

    Examples:
      councilkey ask "plan a trip"                 # 3 agents + vote (together)
      councilkey ask "..." --strategy weighted     # weighted voting
      councilkey ask "..." --alone hermes          # single agent
      councilkey ask "..." --decompose             # split into subtasks
      councilkey ask "..." --debate --rounds 3     # iterative debate
      councilkey ask "..." --voice                 # also speak the answer
      councilkey ask "..." --voice en-US-JennyNeural   # pick the voice
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
    if voice:
        _speak(result.get("final", ""), voice=voice if voice is not True else None)
    return 0


def _speak(text: str, voice: str | None = None) -> None:
    """Best-effort TTS of the final answer (Windows: also opens the file).

    `voice` picks a specific edge-tts voice (e.g. en-US-JennyNeural).
    """
    text = (text or "").strip()
    if not text:
        return
    try:
        from council.voice.chat import chat as vc

        res = vc.tts(text, voice=voice, provider="edge")
        if res.get("ok") and res.get("file"):
            print(f"\n🔊 spoken answer saved: {res['file']}")
            if os.name == "nt" and hasattr(os, "startfile"):
                try:
                    os.startfile(res["file"])  # type: ignore[attr-defined]
                except Exception:
                    pass
        else:
            print(f"\n🔇 could not synthesize speech: {res.get('error', 'unknown')}")
    except Exception as exc:
        print(f"\n🔇 voice skipped ({exc}) - install with: pip install edge-tts")


def cmd_demo(port: int = 8443, open_browser: bool = False) -> int:
    """Run the council in DEMO mode - no API key needed.

    Starts a local demo AI server (deterministic replies) and the dashboard,
    so you can try the 3-agent council immediately. For real answers run:
      councilkey setup   (paste your API key, stored encrypted)
      councilkey serve
    """
    import subprocess as sp
    import tempfile
    import time

    import httpx

    demo_script = ROOT / "scripts" / "dev" / "llm-demo-server.py"
    if not demo_script.exists():
        print("❌ demo server script missing - reinstall the project:  pip install -e .")
        return 1

    demo_port = int(os.environ.get("COUNCIL_DEMO_PORT", "11434"))
    print("== CouncilKey-Os DEMO mode ==")
    print(f"  starting the demo AI server on port {demo_port} (no API key needed)...")

    demo_home = Path(tempfile.mkdtemp(prefix="council-demo-"))
    # the dashboard runs in THIS process - the demo env must apply here too
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{demo_port}/v1"
    os.environ["OPENAI_API_KEY"] = "demo-key"
    os.environ["COUNCIL_HOME"] = str(demo_home)

    proc = sp.Popen([sys.executable, str(demo_script), str(demo_port)], env=os.environ.copy())
    try:
        deadline = time.time() + 20
        ok = False
        while time.time() < deadline:
            try:
                r = httpx.get(f"http://127.0.0.1:{demo_port}/v1/models", timeout=1.0)
                if r.status_code == 200:
                    ok = True
                    break
            except Exception:
                time.sleep(0.3)
        if not ok:
            print("❌ demo AI server did not start. Port busy? Set COUNCIL_DEMO_PORT=11435")
            return 1
        print("  ✅ demo AI server is up")
        print("  starting the dashboard - the 3 agents answer with demo voices.")
        print("  NOTE: DEMO replies are simulated. For real answers:")
        print("        councilkey setup   (paste your API key, stored encrypted)")
        print()
        return cmd_serve(host=os.environ.get("COUNCIL_HOST", "0.0.0.0"), port=port, open_browser=open_browser)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        try:
            import shutil

            shutil.rmtree(demo_home, ignore_errors=True)
        except Exception:
            pass


def cmd_status(json_out: bool = False) -> int:
    """One-screen overview: version, provider, agents, storage, journal.

    With --json, prints a machine-readable summary instead.
    """
    from council.agents.installer import status as agents_status
    from council.backup.manager import list_backups
    from council.journal.analyzer import history as journal_history
    from council.llm.provider import active_provider
    from council.secrets.vault import vault_status

    data = agents_status()
    summary: dict[str, Any] = {
        "version": cmd_version(),
        "provider": active_provider(),
        "agents": {
            name: {
                "state": info["state"],
                "install": info["install"],
                "runtime": info["runtime"],
                "data": info.get("data"),
                "on_stick": info.get("on_stick", False),
            }
            for name, info in data.items()
        },
        "storage": {},
        "journal": {},
        "vault": {},
        "backups": [],
    }
    try:
        from council.storage.optimizer import audit

        report = audit()
        keep = report.get("keep", {})
        cache = report.get("cache", {})
        total_keep = sum(v.get("size", 0) for v in keep.values()) if isinstance(keep, dict) else 0
        total_cache = sum(v.get("size", 0) for v in cache.values()) if isinstance(cache, dict) else 0
        summary["storage"] = {"keep_bytes": total_keep, "cache_bytes": total_cache}
    except Exception:
        pass
    try:
        entries = journal_history(limit=5)
        summary["journal"] = {"recent": len(entries), "last": entries[0]["file"] if entries else None}
    except Exception:
        pass
    try:
        vs = vault_status()
        summary["vault"] = {"keys": vs.get("entries", 0), "backend": vs.get("backend")}
    except Exception:
        pass
    try:
        summary["backups"] = list_backups().get("backups", [])
    except Exception:
        pass

    if json_out:
        print(json.dumps(summary, indent=2, default=str))
        return 0

    print("============================================================")
    print(f" CouncilKey-Os {cmd_version()}")
    print("============================================================")

    # provider
    provider = summary["provider"]
    print(f"\nmodel provider : {provider or 'none (run: councilkey setup)'}")

    # agents
    installed = [n for n, i in summary["agents"].items() if i["state"] == "installed"]
    print(f"agents         : {len(installed)}/{len(summary['agents'])} installed"
          + (f" ({', '.join(sorted(installed))})" if installed else ""))
    for name, info in summary["agents"].items():
        if info["state"] != "installed":
            continue
        stick = " ✔ stick" if info.get("on_stick") else ""
        print(f"    {name:<10} {info['runtime'][:44]}{stick}")

    # storage
    if summary["storage"]:
        print(f"\nstorage        : keep {_human_bytes(summary['storage']['keep_bytes'])}"
              f" | cache {_human_bytes(summary['storage']['cache_bytes'])}"
              " (run 'councilkey storage' to clean)")

    # journal
    if summary["journal"].get("recent"):
        print(f"journal        : {summary['journal']['recent']} recent entries"
              f" - last: {summary['journal']['last']}")

    # vault + backups
    if summary["vault"]:
        print(f"vault          : {summary['vault']['keys']} keys stored"
              f" (encrypted, {summary['vault']['backend']})")
    print(f"backups        : {len(summary['backups'])} available (run 'councilkey backup create')")

    print("\nquick actions:")
    print("  councilkey ask \"your question\"   # 3 agents + vote")
    print("  councilkey serve                 # dashboard")
    print("  councilkey demo                  # try without an API key")
    print("  councilkey setup                 # add/change your API key")
    print("  councilkey doctor                # full health check")
    return 0


def _human_bytes(n: int) -> str:
    n = int(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def cmd_backup(action: str, name: str | None = None, json_out: bool = False) -> int:
    """Create / list / restore encrypted-data backups."""
    from council.backup.manager import create_backup, list_backups, restore_backup

    if action == "create":
        res = create_backup()
        if json_out:
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        if res.get("ok"):
            print(f"✅ backup created: {res.get('path')} ({_human_bytes(res.get('size', 0))})")
            return 0
        print(f"❌ backup failed: {res.get('error', 'unknown')}")
        return 1
    if action == "list":
        backups = list_backups().get("backups", [])
        if json_out:
            print(json.dumps({"backups": backups}, indent=2))
            return 0
        if not backups:
            print("(no backups yet - run: councilkey backup create)")
            return 0
        for b in backups:
            print(f"  {b}")
        return 0
    if action == "restore":
        if not name:
            print("usage: councilkey backup restore <name>   (see 'councilkey backup list')", file=sys.stderr)
            return 2
        res = restore_backup(name)
        if res.get("ok"):
            print(f"✅ restored from {name}")
            return 0
        print(f"❌ restore failed: {res.get('error', 'unknown')}", file=sys.stderr)
        return 1
    print(f"unknown backup action {action!r}", file=sys.stderr)
    return 2


def cmd_journal(action: str, limit: int, json_out: bool = False) -> int:
    """Browse the council journal (what the council decided, and when)."""
    from council.journal.analyzer import analyze, history

    if action == "stats":
        stats = analyze()
        if json_out:
            print(json.dumps(stats, indent=2, default=str))
            return 0
        total = stats.get("total_entries", 0)
        print(f"journal entries : {total}")
        strategies = stats.get("strategies", {})
        if strategies:
            print("strategies      : " + ", ".join(f"{k} x{v}" for k, v in strategies.items()))
        best = stats.get("best_agents", {})
        if best:
            print("best agents     : " + ", ".join(f"{k} x{v}" for k, v in best.items()))
        print(f"consensus       : {stats.get('consensus_reached', 0)} yes / {stats.get('consensus_missed', 0)} no")
        return 0
    # action == "list"
    entries = history(limit)
    if json_out:
        print(json.dumps({"entries": entries}, indent=2, default=str))
        return 0
    if not entries:
        print("(journal is empty - ask the council something first: councilkey ask \"...\")")
        return 0
    for e in entries:
        ts = e.get("timestamp", "?")
        if isinstance(ts, list):
            ts = "-".join(str(t) for t in ts)
        print(f"\n[{ts}] {e.get('file')}")
        print(f"  Q: {e.get('prompt', '')}")
        final = e.get("final", "")
        print(f"  A: {final[:120]}{'...' if len(final) > 120 else ''}")
    return 0


def cmd_pendrive_check(path: str, json_out: bool = False) -> int:
    """Health-check a CouncilKey-Os pendrive: files, venv, data, version."""
    p = Path(path)
    if not p.is_dir():
        if json_out:
            print(json.dumps({"ok": False, "error": "not a directory"}))
            return 1
        print(f"❌ {path} is not a directory - plug in the pendrive first.", file=sys.stderr)
        return 1

    required = [
        "START.bat", "AGENTS.bat", "PENDRIVE-README.txt", "autorun.inf",
        "RUN-OPENCLAW.bat", "RUN-HERMES.bat", "RUN-OPENCODE.bat",
        "RUN-CREWAI.bat", "RUN-AIDER.bat",
        "START-SESSION.bat", "END-SESSION.bat",
    ]
    missing = [f for f in required if not (p / f).exists()]

    stick_venv = p / "CouncilKey-Os" / ".venv"
    venv_py = stick_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not venv_py.exists():
        missing.append("CouncilKey-Os/.venv (portable python)")

    data_dir = p / "council-data"
    data_size = 0
    data_parts: list[str] = []
    if data_dir.is_dir():
        for child in sorted(data_dir.iterdir()):
            if child.is_dir():
                data_parts.append(child.name)
                for f in child.rglob("*"):
                    if f.is_file():
                        try:
                            data_size += f.stat().st_size
                        except OSError:
                            pass
    else:
        missing.append("council-data (data dir)")

    # deep test: can the stick venv actually import the app? (this is what
    # START.bat does - a broken/incomplete venv is why the window closes)
    venv_ok = venv_py.exists()
    if venv_ok:
        try:
            import subprocess as _sp

            r = _sp.run(
                [str(venv_py), "-c", "import council, uvicorn"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                venv_ok = False
                missing.append("app import fails in stick venv (incomplete build)")
        except Exception as exc:
            venv_ok = False
            missing.append(f"app import test error: {exc}")

    # per-agent stick binaries (installed ON the stick, not the PC)
    agent_binaries = {
        "hermes": stick_venv / ("Scripts/hermes.exe" if os.name == "nt" else "bin/hermes"),
        "openclaw": p / "CouncilKey-Os" / "tools" / "openclaw" / "node_modules" / ".bin" / ("openclaw.cmd" if os.name == "nt" else "openclaw"),
        "opencode": p / "CouncilKey-Os" / "tools" / "opencode" / "node_modules" / ".bin" / ("opencode.cmd" if os.name == "nt" else "opencode"),
        "crewai": stick_venv / ("Scripts/crewai.exe" if os.name == "nt" else "bin/crewai"),
        "aider": stick_venv / ("Scripts/aider.exe" if os.name == "nt" else "bin/aider"),
    }
    agents_on_stick = {
        name: binpath.exists() for name, binpath in agent_binaries.items()
    }

    result = {
        "ok": not missing,
        "path": str(p),
        "missing": missing,
        "launchers": {f: (p / f).exists() for f in required},
        "venv": venv_ok,
        "app_imports": venv_ok,
        "agents_on_stick": agents_on_stick,
        "data": {"size_bytes": data_size, "parts": data_parts},
    }
    if json_out:
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    print("==============================================")
    print(f" CouncilKey-Os pendrive check: {path}")
    print("==============================================")
    for f in required:
        mark = "✅" if (p / f).exists() else "❌"
        print(f"  {mark} {f}")
    print(f"  {'✅' if venv_ok else '❌'} CouncilKey-Os/.venv (portable python + app imports)")
    print("  agents on the stick:")
    for name, present in agents_on_stick.items():
        print(f"    {'✅' if present else '⚪'} {name}")
    if data_dir.is_dir():
        print(f"  ✅ council-data/  ({_human_bytes(data_size)}): {', '.join(data_parts) if data_parts else 'empty'}")
    else:
        print("  ❌ council-data/")
    if missing:
        print("\n❌ NOT READY - missing:", ", ".join(missing))
        print("   rebuild the stick:  councilkey pendrive <path>   (or pendrive-setup.ps1)")
        return 1
    print("\n✅ Pendrive ready - plug it into any PC and double-click START.bat")
    return 0


QUICKSTART = """\
CouncilKey-Os - quick start
===========================
1. TRY IT (no key needed):
     councilkey demo                -> dashboard + 3 demo agents, vote 3/3

2. ADD YOUR API KEY (one key powers the whole council):
     councilkey setup               -> wizard: OpenAI / Anthropic / Gemini / OpenRouter
   the key is stored ENCRYPTED in the vault (councilkey key list)

3. ASK THE COUNCIL:
     councilkey ask "your question"             -> 3 agents + vote
     councilkey ask "..." --alone hermes        -> one agent
     councilkey ask "..." --debate --rounds 3   -> debate then vote
     councilkey ask "..." --voice               -> also speak the answer

4. DASHBOARD:
     councilkey serve [--open]      -> http://localhost:8443

5. USB PENDRIVE (the main event):
     councilkey pendrive E:\\ --wizard      -> build the whole stick
     councilkey pendrive-check E:\\         -> is the stick ready?
     councilkey pendrive-push E:\\          -> mirror your keys/memory onto it
   plug into any PC -> double-click START.bat (or AGENTS.bat for a menu)

6. EVERYTHING ELSE:
     councilkey status             one-screen overview
     councilkey journal list       what the council decided
     councilkey backup create      backup your data
     councilkey agents verify      real check of all agents
     councilkey update             pull the latest version

Need help on any step?  councilkey doctor   (health check + hints)
"""


def cmd_wiki(topic: str | None = None) -> int:
    """Print the quick-start guide (or a specific topic) from the CLI."""
    if topic:
        topics = {
            "setup": "councilkey setup    # wizard: provider + encrypted API key\n"
                     "  --provider openai|anthropic|gemini|openrouter|none\n"
                     "  --api-key sk-...   # non-interactive\n"
                     "  --no-agents --skip-tests --skip-verify\n",
            "pendrive": "councilkey which            # are you on the PC copy or the pendrive?\n"
                        "councilkey pendrive E:\\ --wizard     # build the stick (Windows)\n"
                        "councilkey pendrive /media/USB --wizard   # Linux\n"
                        "councilkey pendrive-push E:\\        # mirror keys/journal/memory\n"
                        "councilkey pendrive-check E:\\       # health-check the stick\n"
                        "On the stick: START.bat (dashboard) / AGENTS.bat (menu)\n"
                        "Session mode: START-SESSION.bat clones to PC, END-SESSION.bat wipes it.\n"
                        "Run FROM the stick: E:\\CouncilKey-Os\\councilkey.bat (its 'which' says PENDRIVE)\n",
            "agents": "councilkey agents status     # 5 agents + where their data lives\n"
                      "councilkey agents install    # install all (or: install opencode)\n"
                      "councilkey agents configure opencode   # point it at your API key\n"
                      "councilkey agents verify     # real smoke test (roles + binaries)\n"
                      "councilkey agents env        # export keys for external agents\n",
            "ask": "councilkey ask \"...\"                  # together (majority)\n"
                   "  --strategy weighted|llm_judge|hermes_decides\n"
                   "  --alone hermes|openclaw|opencode\n"
                   "  --decompose   # split into role subtasks\n"
                   "  --debate --rounds N\n"
                   "  --voice       # speak the final answer\n",
            "backup": "councilkey backup create            # tar.gz of journal/memory/secrets\n"
                      "councilkey backup list\n"
                      "councilkey backup restore <name>\n",
            "journal": "councilkey journal list [--limit N]   # recent decisions\n"
                       "councilkey journal stats              # strategies + consensus counts\n",
            "update": "councilkey update   # git pull + reinstall\n"
                      "then:  git checkout main && git pull   # if on a leftover branch\n",
        }
        if topic not in topics:
            print(f"unknown topic {topic!r} - try: {', '.join(sorted(topics))}", file=sys.stderr)
            return 2
        print(topics[topic])
        return 0
    print(QUICKSTART)
    return 0


def cmd_init(path: str) -> int:
    """Initialize an empty council home / data folder on any path.

    Creates the full council-data structure (journal, secrets, memory,
    agent workspaces, backups) so you can point COUNCIL_HOME at it and
    start fresh - or prepare an empty stick for 'councilkey pendrive-push'.
    """
    p = Path(path).expanduser()
    if p.exists() and not p.is_dir():
        print(f"❌ {path} exists and is not a directory", file=sys.stderr)
        return 1
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"❌ cannot create {path}: {exc}", file=sys.stderr)
        return 1

    # canonical storage layout (same as the app creates on startup):
    # journal/secrets/shared/council + per-agent keep/cache + backups
    for rel in (
        "journal", "secrets", "shared", "council", "backups",
        "hermes/keep", "hermes/cache",
        "openclaw/keep", "openclaw/cache",
        "opencode/keep", "opencode/cache",
        "crewai/keep", "aider/keep",
    ):
        try:
            (p / rel).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"⚠ could not create {rel}: {exc}", file=sys.stderr)

    readme = p / "README.txt"
    if not readme.exists():
        readme.write_text(
            "CouncilKey-Os data folder\n"
            "=========================\n"
            "This folder holds the council's data: journal, memory, API keys\n"
            "(encrypted), agent workspaces and backups.\n\n"
            "Point the council at it with:\n"
            "  set COUNCIL_HOME=<this path>     (Windows)\n"
            "  export COUNCIL_HOME=<this path>  (Linux/macOS)\n\n"
            "Then run: councilkey setup   and   councilkey serve\n",
            encoding="utf-8",
        )

    dirs = sorted(d.name for d in p.iterdir() if d.is_dir()) if p.is_dir() else []
    print(f"✅ initialized council home at {p}")
    print(f"   folders: {', '.join(dirs) if dirs else '(empty)'}")
    print("   point COUNCIL_HOME here, then run: councilkey setup")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="councilkey", description="CouncilKey-Os control tool")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="run the dashboard + API server")
    p_serve.add_argument("--host", default=os.environ.get("COUNCIL_HOST", "0.0.0.0"))
    p_serve.add_argument("--port", type=int, default=int(os.environ.get("COUNCIL_PORT", "8443")))
    p_serve.add_argument("--open", action="store_true", help="open the browser automatically")

    p_demo = sub.add_parser("demo", help="try the council NOW - no API key needed (demo voices)")
    p_demo.add_argument("--port", type=int, default=int(os.environ.get("COUNCIL_PORT", "8443")))
    p_demo.add_argument("--open", action="store_true", help="open the browser automatically")

    p_status = sub.add_parser("status", help="one-screen overview of the whole council")
    p_status.add_argument("--json", action="store_true", help="machine-readable output")

    p_wiki = sub.add_parser("wiki", help="print the quick-start guide (or a topic)")
    p_wiki.add_argument("topic", nargs="?", help="setup|pendrive|agents|ask|backup|journal|update")

    p_init = sub.add_parser("init", help="initialize an empty council data folder on any path")
    p_init.add_argument("path", help="folder to initialize (e.g. E:\\council-data or ~/council)")

    sub.add_parser("doctor", help="environment health check")
    sub.add_parser("update", help="pull the latest code + reinstall (git pull)")

    p_storage = sub.add_parser("storage", help="storage audit/optimize")
    p_storage.add_argument("--dry-run", action="store_true", help="only report, don't delete")

    sub.add_parser("version", help="print version")
    sub.add_parser("which", help="show where this CLI is installed (PC vs pendrive)")

    p_agents = sub.add_parser("agents", help="manage the 3 agents (status/install/start/env/configure/verify)")
    p_agents.add_argument("action", nargs="?", default="status",
                          choices=["status", "install", "start", "env", "configure", "verify"])
    p_agents.add_argument("names", nargs="*", help="agent names (default: all)")

    p_key = sub.add_parser("key", help="show/list API keys from the encrypted vault")
    p_key.add_argument("action", nargs="?", default="list", choices=["list", "show"],
                       help="list = masked names (default), show = print one key (for launchers)")
    p_key.add_argument("name", nargs="?", help="key name to print, e.g. OPENROUTER_API_KEY")

    p_llm = sub.add_parser("llm", help="manage the local LLM backend (status/install/pull)")
    p_llm.add_argument("action", nargs="?", default="status", choices=["status", "install", "pull"])
    p_llm.add_argument("model", nargs="?", help="model to pull (default: qwen2.5:3b)")

    p_ask = sub.add_parser("ask", help="ask the council - ALL 3 agents at once + vote")
    p_ask.add_argument("prompt", help="the question to ask")
    p_ask.add_argument("--strategy", default="majority", choices=["majority", "weighted", "llm_judge", "hermes_decides"])
    p_ask.add_argument("--alone", metavar="AGENT", help="ask a single agent (hermes/openclaw/opencode)")
    p_ask.add_argument("--decompose", action="store_true", help="split into role-based subtasks")
    p_ask.add_argument("--debate", action="store_true", help="iterative multi-round debate")
    p_ask.add_argument("--rounds", type=int, default=3, help="debate rounds (default 3)")
    p_ask.add_argument("--voice", nargs="?", const=True, metavar="VOICE",
                       help="also speak the final answer (edge-tts); optionally pick a voice, e.g. en-US-JennyNeural")

    p_pendrive = sub.add_parser("pendrive", help="one-command setup of everything onto a USB stick")
    p_pendrive.add_argument("path", help="mount point of the pendrive (e.g. /media/USB)")
    p_pendrive.add_argument("--wizard", action="store_true", help="also run the API-key wizard into the stick")
    p_pendrive.add_argument("--check", action="store_true", help="check prerequisites + internet first, install NOTHING")
    p_pendrive.add_argument("--agents", metavar="LIST", help="only install these agents (e.g. 1,3,5 or hermes,opencode; default: asks you)")

    p_push = sub.add_parser("pendrive-push", help="build the stick AND copy this PC's data (keys, journal, memory) onto it")
    p_push.add_argument("path", help="mount point of the pendrive (e.g. /media/USB or E:\\)")
    p_push.add_argument("--data-only", action="store_true", help="only copy the data, skip rebuilding the stick")

    p_setup = sub.add_parser("setup", help="interactive setup wizard (provider, API keys, agents)")
    p_setup.add_argument("--provider", choices=["openai", "anthropic", "gemini", "openrouter", "none"],
                         help="model provider for the council + external agents")
    p_setup.add_argument("--api-key", help="API key for the provider (stored encrypted)")
    p_setup.add_argument("--no-agents", action="store_true", help="skip external agent installs")
    p_setup.add_argument("--skip-tests", action="store_true", help="don't run pytest at the end")
    p_setup.add_argument("--skip-verify", action="store_true", help="don't run the council verification at the end")

    p_backup = sub.add_parser("backup", help="create/list/restore backups of your council data")
    p_backup.add_argument("action", nargs="?", default="list", choices=["list", "create", "restore"])
    p_backup.add_argument("name", nargs="?", help="backup name (for restore)")
    p_backup.add_argument("--json", action="store_true", help="machine-readable output")

    p_journal = sub.add_parser("journal", help="browse the council journal (what was decided)")
    p_journal.add_argument("action", nargs="?", default="list", choices=["list", "stats"])
    p_journal.add_argument("--limit", type=int, default=10, help="how many entries to show (default 10)")
    p_journal.add_argument("--json", action="store_true", help="machine-readable output")

    p_pcheck = sub.add_parser("pendrive-check", help="health-check a CouncilKey-Os pendrive")
    p_pcheck.add_argument("path", help="mount point of the pendrive (e.g. E:\\ or /media/USB)")
    p_pcheck.add_argument("--json", action="store_true", help="machine-readable output")

    args = parser.parse_args(argv)

    if args.version:
        print(cmd_version())
        return

    if args.command == "serve":
        sys.exit(cmd_serve(args.host, args.port, open_browser=args.open))
    elif args.command == "demo":
        sys.exit(cmd_demo(port=args.port, open_browser=args.open))
    elif args.command == "status":
        sys.exit(cmd_status(json_out=args.json))
    elif args.command == "wiki":
        sys.exit(cmd_wiki(args.topic))
    elif args.command == "init":
        sys.exit(cmd_init(args.path))
    elif args.command == "backup":
        sys.exit(cmd_backup(args.action, args.name, json_out=args.json))
    elif args.command == "journal":
        sys.exit(cmd_journal(args.action, args.limit, json_out=args.json))
    elif args.command == "pendrive-check":
        sys.exit(cmd_pendrive_check(args.path, json_out=args.json))
    elif args.command == "ask":
        sys.exit(cmd_ask(
            prompt=args.prompt,
            strategy=args.strategy,
            mode="alone" if args.alone else "together",
            agent=args.alone,
            decompose=args.decompose,
            debate=args.debate,
            rounds=args.rounds,
            voice=args.voice,
        ))
    elif args.command == "doctor":
        sys.exit(cmd_doctor())
    elif args.command == "update":
        sys.exit(cmd_update())
    elif args.command == "storage":
        sys.exit(cmd_storage(args.dry_run))
    elif args.command == "agents":
        sys.exit(cmd_agents(args.action, args.names))
    elif args.command == "key":
        sys.exit(cmd_key(args.action, [args.name] if args.name else []))
    elif args.command == "llm":
        sys.exit(cmd_llm(args.action, args.model))
    elif args.command == "pendrive-push":
        from council.agents.pendrive_push import push

        sys.exit(push(args.path, skip_builder=args.data_only))
    elif args.command == "pendrive":
        import subprocess

        # Windows users get the PowerShell builder; unix gets bash
        if os.name == "nt":
            script = ROOT / "scripts" / "pendrive-setup.ps1"
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Path", args.path]
            if args.wizard:
                cmd.append("-Wizard")
            if args.check:
                cmd.append("-Check")
            if args.agents:
                cmd.extend(["-Agents", args.agents])
        else:
            script = ROOT / "scripts" / "pendrive-setup.sh"
            cmd = [str(script), args.path]
            if args.wizard:
                cmd.append("--wizard")
            if args.check:
                cmd.append("--check")
            if args.agents:
                cmd.extend(["--agents", args.agents])
        sys.exit(subprocess.call(cmd))
    elif args.command == "setup":
        from council.agents.setup_wizard import run_wizard

        sys.exit(run_wizard(
            provider=args.provider,
            api_key=args.api_key,
            no_agents=args.no_agents,
            skip_tests=args.skip_tests,
            skip_verify=args.skip_verify,
        ))
    elif args.command == "version":
        print(cmd_version())
        print(f"  installed at: {cmd_which()}")
    elif args.command == "which":
        print(cmd_which())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
