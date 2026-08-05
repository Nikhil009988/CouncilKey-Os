"""CouncilKey-Os CLI - serve, doctor, storage, version.

Commands:
  councilkey serve [--host H] [--port P]     Run the dashboard + API
  councilkey doctor                           Check environment health
  councilkey storage [--dry-run]              Audit / optimize storage
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
    elif args.command == "version":
        print(cmd_version())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
