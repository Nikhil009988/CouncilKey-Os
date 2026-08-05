"""CouncilKey-Os agent installer - download, configure and start the 3 agents.

Agents are fetched from their official upstream repositories:
- hermes     https://github.com/NousResearch/hermes-agent   (Python)
- openclaw   https://github.com/openclaw/openclaw           (Node/npm)
- agent-zero https://github.com/agent0ai/agent-zero         (Python)

Everything is installed under COUNCIL_AGENTS_DIR (default: <repo>/tools/linux)
so the whole setup can be copied to a pendrive, matching the portable layout.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = Path(os.environ.get("COUNCIL_AGENTS_DIR", REPO_ROOT / "tools" / "linux"))

AGENTS: dict[str, dict[str, Any]] = {
    "hermes": {
        "repo": "https://github.com/NousResearch/hermes-agent.git",
        "port": 18790,
        "role": "memory",
        "runtime": "python",
        "start_hint": "cd tools/linux/hermes && uv run hermes   (native Windows supported; official docs: hermes-agent.nousresearch.com)",
    },
    "openclaw": {
        "repo": "https://github.com/openclaw/openclaw.git",
        "port": 18789,
        "role": "action",
        "runtime": "node",
        "start_hint": "openclaw   (prebuilt CLI installed globally - works in PowerShell/cmd)",
    },
    "agent-zero": {
        "repo": "https://github.com/agent0ai/agent-zero.git",
        "port": 50001,
        "role": "builder",
        "runtime": "python",
        "start_hint": "cd tools/linux/agent-zero && python agent.py   (or use their API server)",
    },
}

# ------------------------------------------------------------------ helpers
def _probe(port: int, timeout: float = 1.0) -> tuple[bool, int | None, str | None]:
    """Check whether anything answers on the agent's gateway port."""
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/", timeout=timeout)
        return True, r.status_code, None
    except Exception as exc:
        return False, None, str(exc)


def _run(cmd: list[str], cwd: Path, timeout: int = 900) -> tuple[bool, str]:
    """Run a command, returning (ok, tail-of-output)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        tail = (proc.stdout or "")[-600:] + (proc.stderr or "")[-600:]
        return proc.returncode == 0, tail.strip()
    except Exception as exc:
        return False, str(exc)


# ------------------------------------------------------------ public API
def check_prereqs() -> dict[str, bool]:
    """Which system tools are available (git, python, node, npm, uv)."""
    return {
        "git": shutil.which("git") is not None,
        "python3": sys.executable is not None,
        "node": shutil.which("node") is not None,
        "npm": shutil.which("npm") is not None,
        "uv": shutil.which("uv") is not None,
    }


def status(names: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Per-agent: installed? running? which port/role?"""
    out: dict[str, dict[str, Any]] = {}
    for name, info in AGENTS.items():
        if names and name not in names:
            continue
        agent_dir = AGENTS_DIR / name
        reachable, code, err = _probe(info["port"])
        installed = agent_dir.exists()
        out[name] = {
            "role": info["role"],
            "port": info["port"],
            "runtime": info["runtime"],
            "repo": info["repo"],
            "installed": installed,
            "dir": str(agent_dir) if installed else None,
            "running": reachable,
            "http_status": code,
            "probe_error": err,
            "state": "running" if reachable else ("installed" if installed else "not installed"),
        }
    return out


def install(name: str, update: bool = False) -> dict[str, Any]:
    """Download + configure one agent. Returns a step-by-step report.

    Downloading a big repository takes minutes on a real connection; on a
    machine without internet the clone fails cleanly and tells the user what
    to do once connectivity exists. A `.council-installed` marker records
    that the dependency step completed, so re-runs don't repeat it.
    """
    if name not in AGENTS:
        return {"ok": False, "error": f"unknown agent {name!r} - choose from {sorted(AGENTS)}"}
    info = AGENTS[name]
    agent_dir = AGENTS_DIR / name
    marker = agent_dir / ".council-installed"
    steps: list[dict[str, Any]] = []

    if agent_dir.exists() and marker.exists() and not update:
        return {
            "ok": True,
            "name": name,
            "already_installed": True,
            "dir": str(agent_dir),
            "steps": [{"step": "install", "ok": True, "detail": "already installed"}],
        }

    # 1. clone (or pull when updating)
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    if agent_dir.exists() and (update or not marker.exists()):
        if not (agent_dir / ".git").exists():
            # broken/partial clone - redo it
            import shutil as _sh

            _sh.rmtree(agent_dir, ignore_errors=True)
        else:
            ok, tail = _run(["git", "pull", "--ff-only"], agent_dir, timeout=300)
            steps.append({"step": "pull", "ok": ok, "detail": tail or "up to date"})
    if not agent_dir.exists():
        ok, tail = _run(
            ["git", "clone", "--depth", "1", "--branch", "main", info["repo"], str(agent_dir)],
            AGENTS_DIR,
            timeout=900,
        )
        steps.append({"step": "clone", "ok": ok, "detail": tail or f"cloned into {agent_dir}"})
        if not ok:
            return {
                "ok": False,
                "name": name,
                "error": f"clone failed (no internet?): {tail[:300]}",
                "steps": steps,
                "hint": "retry later with: councilkey agents install " + name,
            }

    # 2. dependencies (best effort - each agent repo documents its own way)
    if info["runtime"] == "python":
        steps.append(_install_python_deps(agent_dir))
    else:
        steps.append(_install_node_deps(agent_dir))
        # OpenClaw source trees are NOT built - the prebuilt npm package is
        # the reliable way to get a working `openclaw` command (this is what
        # fixes 'missing dist/entry.mjs' errors in PowerShell).
        if name == "openclaw" and shutil.which("npm"):
            steps.append(_install_openclaw_cli())

    ok_all = all(s.get("ok") for s in steps[1:]) if len(steps) > 1 else True
    if ok_all:
        try:
            marker.write_text("ok", encoding="utf-8")
        except OSError:
            pass
    return {
        "ok": ok_all,
        "name": name,
        "dir": str(agent_dir),
        "steps": steps,
        "next": f"start it with: councilkey agents start {name}",
    }


def _install_python_deps(agent_dir: Path) -> dict[str, Any]:
    req = agent_dir / "requirements.txt"
    if not req.exists():
        # some repos (e.g. Hermes) use uv/pyproject only
        if shutil.which("uv"):
            ok, tail = _run(["uv", "sync"], agent_dir, timeout=1800)
            return {"step": "deps", "ok": ok, "detail": (tail or "uv sync done")[:300]}
        return {"step": "deps", "ok": True, "detail": "no requirements.txt - install with 'uv sync' (see the agent's README)"}
    venv = agent_dir / ".venv"
    if not venv.exists():
        ok, tail = _run([sys.executable, "-m", "venv", str(venv)], agent_dir, timeout=300)
        if not ok:
            return {"step": "deps", "ok": False, "detail": f"venv failed: {tail[:200]}"}
    pip = venv / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
    # fresh venvs ship old pip/setuptools which fail on modern pyproject
    # metadata - upgrade first (this alone fixes most install failures)
    _run([str(pip), "install", "-q", "--upgrade", "pip", "setuptools", "wheel"], agent_dir, timeout=300)
    ok, tail = _run([str(pip), "install", "-q", "-r", str(req)], agent_dir, timeout=1800)
    return {"step": "deps", "ok": ok, "detail": (tail or "deps installed")[:300]}


def _install_node_deps(agent_dir: Path) -> dict[str, Any]:
    pkg = agent_dir / "package.json"
    if not pkg.exists():
        return {"step": "deps", "ok": True, "detail": "no package.json"}
    if shutil.which("npm") is None:
        return {"step": "deps", "ok": False, "detail": "npm not installed - install Node.js first"}
    ok, tail = _run(["npm", "install", "--no-audit", "--no-fund"], agent_dir, timeout=1800)
    return {"step": "deps", "ok": ok, "detail": (tail or "npm install done")[:300]}


def _install_openclaw_cli() -> dict[str, Any]:
    """Install the prebuilt OpenClaw CLI globally (npm) - the supported way."""
    ok, tail = _run(["npm", "install", "-g", "openclaw@latest"], Path.home(), timeout=1800)
    detail = tail or "openclaw CLI installed"
    if ok:
        version = _run(["openclaw", "--version"], Path.home(), timeout=30)
        detail = f"openclaw CLI ready: {version[1][:60]}"
    return {"step": "cli", "ok": ok, "detail": detail[:300]}


def start(name: str, wait: int = 30) -> dict[str, Any]:
    """Best-effort: launch an installed agent's gateway and wait for its port.

    Looks for the usual launchers inside the agent directory. If none is
    found it tells the user how to start it manually (each agent repo ships
    its own README with the canonical command).
    """
    if name not in AGENTS:
        return {"ok": False, "error": f"unknown agent {name!r} - choose from {sorted(AGENTS)}"}
    info = AGENTS[name]
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        return {
            "ok": False,
            "error": f"{name} is not installed - run: councilkey agents install {name}",
        }
    already, _, _ = _probe(info["port"])
    if already:
        return {"ok": True, "name": name, "already_running": True, "port": info["port"]}

    candidates: list[tuple[str, Path]] = [
        ("python", agent_dir / "gateway.py"),
        ("python", agent_dir / "main.py"),
        ("python", agent_dir / "src" / "gateway.py"),
        ("python", agent_dir / "src" / "main.py"),
        ("python", agent_dir / "agent.py"),
        ("sh", agent_dir / "start.sh"),
        ("sh", agent_dir / "run.sh"),
        ("node", agent_dir / "openclaw.mjs"),
    ]
    log_path = agent_dir / "council-agent.log"
    for kind, script in candidates:
        if not script.exists():
            continue
        if kind == "node":
            cmd = [shutil.which("node") or "node", str(script)]
        elif kind == "python":
            cmd = [sys.executable, str(script)]
        else:
            cmd = ["bash", str(script)]
        try:
            with open(log_path, "a", encoding="utf-8") as log:
                subprocess.Popen(
                    cmd,
                    cwd=agent_dir,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except Exception:
            continue
        deadline = time.time() + wait
        while time.time() < deadline:
            up, _, _ = _probe(info["port"], timeout=0.8)
            if up:
                return {
                    "ok": True,
                    "name": name,
                    "launcher": str(script),
                    "port": info["port"],
                    "log": str(log_path),
                }
            time.sleep(1)
    return {
        "ok": False,
        "name": name,
        "error": f"started no known launcher for {name}",
        "hint": info.get("start_hint", "start it manually per its README"),
        "log": str(log_path),
    }
