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
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

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
        "install": "docker-launcher",
        "bin": "a0",
        "role": "builder & review (external, optional)",
        "runtime": "docker",
        "start_hint": "Agent Zero runs where Docker runs. Use the A0 Launcher (see agent-zero.ai)\nor: docker compose up in the agent-zero source tree.",
    },
}

# ------------------------------------------------------------------ helpers
def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> tuple[bool, str]:
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
            installed = _on_path("docker") or _on_path("a0")
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
    if info["install"] == "official-installer":
        return _install_official(info)
    if info["install"] == "docker-launcher":
        return _install_agent_zero(info)
    return {"ok": False, "error": "no installer defined"}


def _install_npm(info: dict[str, Any]) -> dict[str, Any]:
    if shutil.which("npm") is None:
        return {"ok": False, "name": "openclaw",
                "error": "npm not found - install Node.js 18+ first (https://nodejs.org)",
                "hint": "Windows: winget install OpenJS.NodeJS.LTS"}
    print(f"  installing {info['package']} globally (npm)...")
    ok, tail = _run(["npm", "install", "-g", info["package"]], Path.home(), timeout=1800)
    if not ok:
        return {"ok": False, "name": "openclaw", "error": f"npm install failed: {tail[:300]}"}
    ver = _run([info["bin"], "--version"], Path.home(), timeout=30)
    return {"ok": True, "name": "openclaw",
            "steps": [{"step": "npm install -g", "ok": True, "detail": ver[1][:80] or "installed"}],
            "next": "openclaw onboard --install-daemon   # first-run onboarding"}


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
        return {"ok": False, "name": "hermes",
                "error": f"could not fetch the official installer from this machine ({exc})",
                "hint": "run it manually:\n  Linux/macOS: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash\n  Windows:      iex (irm https://hermes-agent.nousresearch.com/install.ps1)"}
    if sys.platform == "win32":
        return {"ok": False, "name": "hermes",
                "error": "run the official PowerShell installer on Windows",
                "hint": "iex (irm https://hermes-agent.nousresearch.com/install.ps1)"}
    print("  running the official installer (this can take several minutes)...")
    try:
        proc = subprocess.run(
            ["bash"],
            input=script,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        tail = (proc.stdout or "")[-600:] + (proc.stderr or "")[-600:]
        ok = proc.returncode == 0
    except Exception as exc:
        return {"ok": False, "name": "hermes", "error": f"installer failed: {exc}"}
    if not ok:
        return {"ok": False, "name": "hermes", "error": f"installer failed: {tail[:300]}"}
    return {"ok": True, "name": "hermes",
            "steps": [{"step": "official installer", "ok": True, "detail": "hermes installed"}],
            "next": "hermes setup   # guided configuration"}


def _install_agent_zero(info: dict[str, Any]) -> dict[str, Any]:
    """Agent Zero runs in Docker. With docker present, clone the source so
    `docker compose up` works; otherwise explain the launcher path."""
    if not _on_path("docker"):
        return {"ok": False, "name": "agent-zero",
                "error": "Agent Zero needs Docker (it runs a full Linux desktop in a container)",
                "hint": "install Docker Desktop (https://docker.com), then the A0 Launcher from agent-zero.ai"}
    src = AGENTS_DIR / "agent-zero"
    if src.exists():
        return {"ok": True, "name": "agent-zero",
                "steps": [{"step": "docker", "ok": True, "detail": "docker found + source present"}],
                "next": "cd tools/linux/agent-zero && docker compose up   (or use the A0 Launcher)"}
    print("  cloning the agent-zero source for Docker...")
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    ok, tail = _run(
        ["git", "clone", "--depth", "1", "https://github.com/agent0ai/agent-zero.git", str(src)],
        AGENTS_DIR,
        timeout=900,
    )
    if not ok:
        return {"ok": False, "name": "agent-zero",
                "error": f"clone failed (no internet?): {tail[:200]}",
                "hint": "download the A0 Launcher from agent-zero.ai instead"}
    return {"ok": True, "name": "agent-zero",
            "steps": [{"step": "docker", "ok": True, "detail": "docker found"}, {"step": "clone", "ok": True, "detail": "source ready"}],
            "next": "cd tools/linux/agent-zero && docker compose up   (or use the A0 Launcher)"}


def start(name: str, wait: int = 30) -> dict[str, Any]:
    """Best-effort: launch an installed agent's interactive CLI is NOT safe to
    daemonize - these are interactive tools. Tell the user how to run them."""
    info = AGENTS.get(name)
    if not info:
        return {"ok": False, "error": f"unknown agent {name!r}"}
    if not (_on_path(info["bin"]) or (name == "agent-zero" and _on_path("docker"))):
        return {"ok": False, "name": name, "error": f"{name} is not installed",
                "hint": f"councilkey agents install {name}"}
    # Interactive CLIs: verify the binary runs, then hand over.
    if name == "openclaw":
        ver = _run([info["bin"], "--version"], Path.home(), timeout=30)
        if ver[0]:
            return {"ok": True, "name": name, "detail": ver[1][:80], "interactive": True,
                    "hint": info["start_hint"]}
    if name == "hermes":
        return {"ok": True, "name": name, "interactive": True, "hint": info["start_hint"]}
    return {"ok": True, "name": name, "interactive": True, "hint": info["start_hint"]}
