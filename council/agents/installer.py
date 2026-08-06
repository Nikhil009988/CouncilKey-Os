"""CouncilKey-Os agent installer - official install methods only.

Each agent is installed the way its own project documents:

- Hermes      official one-liner (hermes-agent.nousresearch.com/install.sh)
              -> `hermes` CLI + messaging gateway. Interactive chat agent.
- OpenClaw    `npm install -g openclaw@latest` -> `openclaw` CLI.
              Multi-channel personal assistant. Interactive chat agent.
- Agent Zero  Docker-based desktop agent. Recommended: the A0 Launcher.
              Detect Docker and give clear instructions.

All three are interactive agents with their own UIs - they are NOT HTTP
services. The council's always-working brains are the local-LLM role agents
(council.llm.agents, powered by Ollama); the external agents are optional
add-ons you use through their own interfaces. When an external agent DOES
expose an HTTP endpoint (e.g. a custom gateway bridge), point the council at
it via COUNCIL_HERMES_URL / COUNCIL_OPENCLAW_URL / COUNCIL_AGENTZERO_URL.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

import httpx

from council.agents.proc import run_cmd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = Path(os.environ.get("COUNCIL_AGENTS_DIR", REPO_ROOT / "tools" / "linux"))

AGENTS: dict[str, dict[str, Any]] = {
    "hermes": {
        "install": "official-installer",
        "installer_url": "https://hermes-agent.nousresearch.com/install.sh",
        "installer_url_win": "https://hermes-agent.nousresearch.com/install.ps1",
        "bin": "hermes",
        "role": "memory & analysis (external, optional)",
        "runtime": "official one-liner",
        "start_hint": "hermes            # interactive chat\nhermes model     # choose your LLM provider\nhermes gateway   # messaging gateway (Telegram/Discord/...)",
    },
    "openclaw": {
        "install": "npm",
        "package": "openclaw@latest",
        "bin": "openclaw",
        "role": "action & execution (external, optional)",
        "runtime": "node/npm",
        "start_hint": "openclaw                     # interactive chat\nopenclaw onboard --install-daemon   # guided onboarding",
    },
    "agent-zero": {
        "install": "source-venv",
        "repo": "https://github.com/agent0ai/agent-zero.git",
        "bin": "agent-zero",
        "role": "builder & review (external, optional)",
        "runtime": "python/venv (no Docker needed for chat; Docker optional for terminal/browser tools)",
        "start_hint": "cd tools/linux/agent-zero && .venv/bin/python agent.py   # interactive chat (needs Python 3.12+)\n# Docker optional: enables the built-in terminal/browser (docker compose up)",
    },
    "crewai": {
        "install": "pip",
        "package": "crewai",
        "bin": "crewai",
        "role": "role-based agent teams (external, optional)",
        "runtime": "python/pip",
        "start_hint": "crewai create crew my_crew   # scaffold a crew\ncd my_crew && crewai run      # run the crew (all agents together)",
    },
    "aider": {
        "install": "pip",
        "package": "aider-chat",
        "bin": "aider",
        "role": "pair-programming chat agent (external, optional)",
        "runtime": "python/pip",
        "start_hint": "aider                # chat in your repo (uses the same API keys)\naider --model gpt-4o-mini   # pick a model",
    },
}

# ------------------------------------------------------------------ helpers
def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> tuple[bool, str]:
    """Cross-platform command runner (handles Windows .cmd/.exe)."""
    return run_cmd(cmd, cwd=cwd, timeout=timeout)


def _on_path(binary: str) -> bool:
    return shutil.which(binary) is not None


# ------------------------------------------------------------ public API
def check_prereqs() -> dict[str, bool]:
    """Which system tools are available for the official installers."""
    return {
        "git": shutil.which("git") is not None,
        "python3": sys.executable is not None,
        "node": shutil.which("node") is not None,
        "npm": shutil.which("npm") is not None,
        "docker": shutil.which("docker") is not None,
        "curl": shutil.which("curl") is not None,
        "ollama": shutil.which("ollama") is not None,
    }


def status(names: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Per-agent: installed (binary on PATH / docker present)? running?"""
    out: dict[str, dict[str, Any]] = {}
    for name, info in AGENTS.items():
        if names and name not in names:
            continue
        binary = info["bin"]
        installed = _on_path(binary)
        # hermes installs under ~/.local/bin (or %LOCALAPPDATA%/hermes)
        if name == "hermes":
            home_bin = Path.home() / ".local" / "bin" / "hermes"
            win_bin = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "hermes.exe"
            installed = installed or home_bin.exists() or win_bin.exists()
        if name == "agent-zero":
            az_dir = AGENTS_DIR / "agent-zero"
            venv_py = az_dir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            installed = installed or (az_dir.exists() and venv_py.exists())
        # crewai/aider install into the project venv
        if name in ("crewai", "aider"):
            venv_bin = REPO_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / binary
            installed = installed or venv_bin.exists()
        out[name] = {
            "role": info["role"],
            "install": info["install"],
            "runtime": info["runtime"],
            "binary": binary,
            "installed": installed,
            "state": "installed" if installed else "not installed",
        }
    return out


def install(name: str) -> dict[str, Any]:
    """Install one agent using its official installer."""
    if name not in AGENTS:
        return {"ok": False, "error": f"unknown agent {name!r} - choose from {sorted(AGENTS)}"}
    info = AGENTS[name]

    if _on_path(info["bin"]) or (name == "agent-zero" and _on_path("docker")):
        return {"ok": True, "name": name, "already_installed": True,
                "steps": [{"step": "check", "ok": True, "detail": f"{info['bin']} already on PATH"}]}

    if info["install"] == "npm":
        return _install_npm(info)
    if info["install"] == "pip":
        return _install_pip(info)
    if info["install"] == "official-installer":
        return _install_official(info)
    if info["install"] == "source-venv":
        return _install_source_venv(info)
    return {"ok": False, "error": "no installer defined"}


def _install_npm(info: dict[str, Any]) -> dict[str, Any]:
    """Install openclaw via npm with Windows-proof command resolution."""
    from council.agents.proc import resolve_cmd, which_resolved

    npm_exe = which_resolved("npm")
    if npm_exe is None:
        return {"ok": False, "name": "openclaw",
                "error": "npm not found - install Node.js 18+ first (https://nodejs.org)",
                "hint": "Windows: winget install OpenJS.NodeJS.LTS   then open a NEW terminal"}
    # Windows: use the resolved npm.cmd path explicitly (avoids WinError 2)
    cmd = [npm_exe, "install", "-g", info["package"]]
    print(f"  installing {info['package']} globally (npm via {npm_exe})...")
    ok, tail = _run(cmd, Path.home(), timeout=1800)
    if not ok:
        return {"ok": False, "name": "openclaw",
                "error": f"npm install failed: {tail[:300]}",
                "hint": f"npm path: {npm_exe}\nrun it manually in a NEW terminal:\n  npm install -g {info['package']}"}
    ver = _run([resolve_cmd(info["bin"]), "--version"], Path.home(), timeout=30)
    return {"ok": True, "name": "openclaw",
            "steps": [{"step": "npm install -g", "ok": True, "detail": ver[1][:80] or "installed"}],
            "next": "openclaw onboard --install-daemon   # first-run onboarding"}


def _install_pip(info: dict[str, Any]) -> dict[str, Any]:
    """Install a pip-based agent (crewai / aider) - official pip package."""
    print(f"  installing {info['package']} via pip (into the project venv)...")
    venv_pip = REPO_ROOT / ".venv" / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
    if venv_pip.exists():
        ok, tail = _run([str(venv_pip), "install", "-q", info["package"]], REPO_ROOT, timeout=1800)
    else:
        ok, tail = _run([sys.executable, "-m", "pip", "install", "-q", info["package"]], REPO_ROOT, timeout=1800)
    if not ok:
        return {"ok": False, "name": info["bin"],
                "error": f"pip install {info['package']} failed: {tail[:300]}"}
    ver = _run([info["bin"], "--version"], REPO_ROOT, timeout=30)
    return {"ok": True, "name": info["bin"],
            "steps": [{"step": f"pip install {info['package']}", "ok": True, "detail": ver[1][:80] or "installed"}],
            "next": info["start_hint"].splitlines()[0]}


def _install_pip_batch(packages: list[str]) -> dict[str, Any]:
    """Install several pip packages in ONE command (much faster than
    installing them one by one - pip resolves shared deps once)."""
    venv_pip = REPO_ROOT / ".venv" / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
    cmd = [str(venv_pip), "install", "-q"] + packages if venv_pip.exists() else           [sys.executable, "-m", "pip", "install", "-q"] + packages
    ok, tail = _run(cmd, REPO_ROOT, timeout=2400)
    return {"ok": ok, "detail": tail[:200] or f"installed: {', '.join(packages)}"}


def _install_official(info: dict[str, Any]) -> dict[str, Any]:
    url = info["installer_url_win"] if sys.platform == "win32" else info["installer_url"]
    print(f"  downloading the official installer: {url}")
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        script = r.content.decode("utf-8", errors="replace")
        if "bash" not in script[:500] and "#!/bin/sh" not in script[:500] and "#!/bin/bash" not in script[:500]:
            raise RuntimeError("downloaded file does not look like a shell installer")
    except Exception as exc:
        # official installer unreachable -> fall back to the official PyPI
        # package (hermes-agent is published by Nous Research)
        print(f"  ⚠ official installer unreachable ({exc}) - falling back to pip install hermes-agent")
        ok, tail = run_cmd([sys.executable, "-m", "pip", "install", "-q", "hermes-agent"],
                           cwd=REPO_ROOT, timeout=1200)
        if ok:
            return {"ok": True, "name": "hermes",
                    "steps": [{"step": "pip install hermes-agent", "ok": True, "detail": "installed (fallback)"}],
                    "next": "hermes setup   # guided configuration"}
        return {"ok": False, "name": "hermes",
                "error": f"could not install hermes ({exc}); pip fallback also failed: {tail[:200]}",
                "hint": "run it manually:\n  Linux/macOS: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash\n  Windows:      iex (irm https://hermes-agent.nousresearch.com/install.ps1)"}
    if sys.platform == "win32":
        return {"ok": False, "name": "hermes",
                "error": "run the official PowerShell installer on Windows",
                "hint": "iex (irm https://hermes-agent.nousresearch.com/install.ps1)"}
    print("  running the official installer (this can take several minutes)...")
    ok, tail = run_cmd(["bash"], cwd=Path.home(), timeout=1800, input_text=script)
    if not ok:
        return {"ok": False, "name": "hermes", "error": f"installer failed: {tail[:300]}"}
    if not ok:
        return {"ok": False, "name": "hermes", "error": f"installer failed: {tail[:300]}"}
    return {"ok": True, "name": "hermes",
            "steps": [{"step": "official installer", "ok": True, "detail": "hermes installed"}],
            "next": "hermes setup   # guided configuration"}


def _install_source_venv(info: dict[str, Any]) -> dict[str, Any]:
    """Install agent-zero like hermes/openclaw: clone the source + create a
    Python venv + install requirements. NO Docker needed for basic use -
    the agent framework runs on the host; Docker only adds the optional
    terminal/browser tools (their hybrid dev approach).

    Note: agent-zero's code uses Python 3.12+ syntax - check before the
    multi-GB dependency install."""
    name = "agent-zero"
    if sys.version_info < (3, 12):
        return {"ok": False, "name": name,
                "error": "agent-zero needs Python 3.12+ (its code uses 3.12 syntax)",
                "hint": "install Python 3.12+ from https://python.org, then re-run: councilkey agents install agent-zero"}
    src = AGENTS_DIR / "agent-zero"
    steps: list[dict[str, Any]] = []

    # 1. clone
    if src.exists() and not (src / ".git").exists():
        shutil.rmtree(src, ignore_errors=True)
    if not src.exists():
        print("  cloning the agent-zero source...")
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        ok, tail = _run(
            ["git", "clone", "--depth", "1", info["repo"], str(src)],
            AGENTS_DIR,
            timeout=900,
        )
        steps.append({"step": "clone", "ok": ok, "detail": tail or "source ready"})
        if not ok:
            return {"ok": False, "name": name,
                    "error": f"clone failed (no internet?): {tail[:200]}",
                    "hint": "retry later with: councilkey agents install agent-zero"}

    # 2. venv + deps (heavy: includes torch - several GB)
    venv = src / ".venv"
    venv_py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not venv_py.exists():
        print("  creating the Python environment (one-time, a few GB)...")
        ok, tail = _run([sys.executable, "-m", "venv", str(venv)], src, timeout=600)
        steps.append({"step": "venv", "ok": ok, "detail": tail or "venv ready"})
        if not ok:
            return {"ok": False, "name": name, "error": f"venv failed: {tail[:200]}"}
    else:
        steps.append({"step": "venv", "ok": True, "detail": "already present"})

    pip = venv / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
    _run([str(pip), "install", "-q", "--upgrade", "pip", "setuptools", "wheel"], src, timeout=300)
    print("  installing agent-zero dependencies (can take several minutes, please wait)...")
    ok, tail = _run([str(pip), "install", "-q", "-r", str(src / "requirements.txt")], src, timeout=1800)
    steps.append({"step": "deps", "ok": ok, "detail": tail[:120] or "deps installed"})
    if not ok:
        return {"ok": False, "name": name,
                "error": f"dependency install failed: {tail[:300]}",
                "hint": "retry: councilkey agents install agent-zero   (partial state is reused)"}

    return {"ok": True, "name": name, "steps": steps,
            "next": "cd tools/linux/agent-zero && .venv/bin/python agent.py   # interactive chat"}


def start(name: str, wait: int = 30) -> dict[str, Any]:
    """Best-effort: launch an installed agent's interactive CLI is NOT safe to
    daemonize - these are interactive tools. Tell the user how to run them."""
    info = AGENTS.get(name)
    if not info:
        return {"ok": False, "error": f"unknown agent {name!r}"}
    if name == "agent-zero":
        az_dir = AGENTS_DIR / "agent-zero"
        venv_py = az_dir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not (az_dir.exists() and venv_py.exists()):
            return {"ok": False, "name": name, "error": "agent-zero is not installed",
                    "hint": "councilkey agents install agent-zero"}
        return {"ok": True, "name": name, "interactive": True, "hint": info["start_hint"],
                "first_run": "python agent.py runs an interactive chat - it will ask for a model provider"}
    if not _on_path(info["bin"]):
        return {"ok": False, "name": name, "error": f"{name} is not installed",
                "hint": f"councilkey agents install {name}"}
    # Interactive CLIs: verify the binary runs, then hand over.
    if name == "openclaw":
        ver = _run([info["bin"], "--version"], Path.home(), timeout=30)
        if ver[0]:
            return {"ok": True, "name": name, "detail": ver[1][:80], "interactive": True,
                    "hint": info["start_hint"],
                    "diagnose": "openclaw doctor",
                    "one_shot": 'openclaw agent -m "your question" --local --agent main',
                    "first_run": "openclaw onboard   (interactive wizard - configure model provider)"}
    if name == "hermes":
        return {"ok": True, "name": name, "interactive": True, "hint": info["start_hint"],
                "first_run": "hermes setup   (interactive wizard - configure model provider)"}
    return {"ok": True, "name": name, "interactive": True, "hint": info["start_hint"]}


def openclaw_local_command() -> str:
    """The one-shot command that makes an installed OpenClaw answer using the
    same local Ollama model as the council - with a placeholder for the message."""
    return "openclaw agent -m \"<your question>\" --local --agent main --model ollama/qwen2.5:3b"
