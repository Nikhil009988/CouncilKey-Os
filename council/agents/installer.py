"""CouncilKey-Os agent installer - official install methods only.

Each agent is installed the way its own project documents:

- Hermes      official one-liner (hermes-agent.nousresearch.com/install.sh)
              -> `hermes` CLI + messaging gateway. Interactive chat agent.
- OpenClaw    `npm install -g openclaw@latest` -> `openclaw` CLI.
              Multi-channel personal assistant. Interactive chat agent.
- Codex       `npm install -g @openai/codex` -> `codex` CLI (OpenHands/OpenAI).
              Local coding agent with terminal, file and web tools - runs on
              your PC, NO Docker needed. Replaces Agent Zero, whose special
              abilities (terminal/browser/sub-agents) required Docker.

All three are interactive agents with their own UIs - they are NOT HTTP
services. The council's always-working brains are the provider role agents
(council.llm.provider); the external agents are optional add-ons you use
through their own interfaces. When an external agent DOES expose an HTTP
endpoint (e.g. a custom gateway bridge), point the council at it via
COUNCIL_HERMES_URL / COUNCIL_OPENCLAW_URL / COUNCIL_CODEX_URL.
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
        "_npm_name": "openclaw",
        "_next": "openclaw onboard --install-daemon   # first-run onboarding",
        "role": "action & execution (external, optional)",
        "runtime": "node/npm",
        "start_hint": "openclaw                     # interactive chat\nopenclaw onboard --install-daemon   # guided onboarding",
    },
    "codex": {
        "install": "npm",
        "package": "@openai/codex",
        "bin": "codex",
        "_npm_name": "codex",
        "_next": "councilkey agents configure codex   # point it at your API key (OpenAI/OpenRouter)",
        "role": "builder & review (external, optional)",
        "runtime": "node/npm - local execution, NO Docker (terminal/file/web tools built in)",
        "start_hint": "codex                     # interactive chat in any folder\ncodex exec \"your task\"      # one-shot task\ncouncilkey agents configure codex   # point it at your API key",
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
        # codex can also live on the pendrive: CouncilKey-Os/tools/codex
        if name == "codex":
            stick_bin = AGENTS_DIR.parent / "codex" / "node_modules" / ".bin" / ("codex.cmd" if os.name == "nt" else "codex")
            installed = installed or stick_bin.exists()
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

    if _on_path(info["bin"]):
        return {"ok": True, "name": name, "already_installed": True,
                "steps": [{"step": "check", "ok": True, "detail": f"{info['bin']} already on PATH"}]}

    if info["install"] == "npm":
        return _install_npm(info)
    if info["install"] == "pip":
        return _install_pip(info)
    if info["install"] == "official-installer":
        return _install_official(info)
    return {"ok": False, "error": "no installer defined"}


def _install_npm(info: dict[str, Any]) -> dict[str, Any]:
    """Install an npm-based agent (openclaw / codex) with Windows-proof
    command resolution."""
    from council.agents.proc import resolve_cmd, which_resolved

    name = info.get("_npm_name", "openclaw")
    npm_exe = which_resolved("npm")
    if npm_exe is None:
        return {"ok": False, "name": name,
                "error": "npm not found - install Node.js first (https://nodejs.org)",
                "hint": "Windows: winget install OpenJS.NodeJS.LTS   then open a NEW terminal"}
    # Windows: use the resolved npm.cmd path explicitly (avoids WinError 2)
    cmd = [npm_exe, "install", "-g", info["package"]]
    print(f"  installing {info['package']} globally (npm via {npm_exe})...")
    ok, tail = _run(cmd, Path.home(), timeout=1800)
    if not ok:
        return {"ok": False, "name": name,
                "error": f"npm install failed: {tail[:300]}",
                "hint": f"npm path: {npm_exe}\nrun it manually in a NEW terminal:\n  npm install -g {info['package']}"}
    ver = _run([resolve_cmd(info["bin"]), "--version"], Path.home(), timeout=30)
    next_hint = info.get("_next", "openclaw onboard --install-daemon   # first-run onboarding")
    return {"ok": True, "name": name,
            "steps": [{"step": "npm install -g", "ok": True, "detail": ver[1][:80] or "installed"}],
            "next": next_hint}


def _install_pip(info: dict[str, Any]) -> dict[str, Any]:
    """Install a pip-based agent (crewai / aider) globally so the command
    works in ANY terminal (Windows: Scripts on PATH via pip's Scripts dir)."""
    print(f"  installing {info['package']} globally via pip (so '{info['bin']}' works in any terminal)...")
    # -m pip installs into the user/global site-packages and puts the exe on
    # PATH (Windows: %APPDATA%\Python\Scripts or the Python Scripts dir)
    ok, tail = _run([sys.executable, "-m", "pip", "install", "-q", info["package"]], REPO_ROOT, timeout=1800)
    if not ok:
        return {"ok": False, "name": info["bin"],
                "error": f"pip install {info['package']} failed: {tail[:300]}",
                "hint": f"run it manually in a NEW terminal:\n  pip install {info['package']}"}
    ver = _run([info["bin"], "--version"], REPO_ROOT, timeout=30)
    return {"ok": True, "name": info["bin"],
            "steps": [{"step": f"pip install {info['package']} (global)", "ok": True, "detail": ver[1][:80] or "installed"}],
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
        # Windows: the official installer is a PowerShell script; prefer the
        # pip fallback (same official package) since it works non-interactively
        print("  ⚠ the official installer is PowerShell-based - falling back to pip install hermes-agent")
        ok, tail = run_cmd([sys.executable, "-m", "pip", "install", "-q", "hermes-agent"],
                           cwd=REPO_ROOT, timeout=1200)
        if ok:
            return {"ok": True, "name": "hermes",
                    "steps": [{"step": "pip install hermes-agent", "ok": True, "detail": "installed (fallback)"}],
                    "next": "hermes setup   # guided configuration"}
        return {"ok": False, "name": "hermes",
                "error": f"pip fallback failed: {tail[:200]}",
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


def start(name: str, wait: int = 30) -> dict[str, Any]:
    """Best-effort: launch an installed agent's interactive CLI is NOT safe to
    daemonize - these are interactive tools. Tell the user how to run them."""
    info = AGENTS.get(name)
    if not info:
        return {"ok": False, "error": f"unknown agent {name!r}"}
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
    if name == "codex":
        return {"ok": True, "name": name, "interactive": True, "hint": info["start_hint"],
                "diagnose": "councilkey agents configure codex",
                "one_shot": 'codex exec "your question"',
                "first_run": "councilkey agents configure codex   (points Codex at your API key)"}
    return {"ok": True, "name": name, "interactive": True, "hint": info["start_hint"]}


# ------------------------------------------------------------- codex config
def configure(name: str = "codex") -> dict[str, Any]:
    """Write the config that points an external agent at the user's provider.

    Codex CLI speaks the OpenAI "Responses" protocol, so it works with the
    OpenAI and OpenRouter providers out of the box (OpenRouter officially
    documents this setup). Gemini/Anthropic keys can't be used by Codex
    directly - we say so clearly instead of writing a broken config.

    The config file goes to $CODECONFIG when set (pendrive mode keeps it on
    the stick), otherwise to ~/.codex/config.toml.
    """
    if name != "codex":
        return {"ok": False, "error": f"configure is only implemented for 'codex' (got {name!r})"}

    from council.llm.provider import active_provider

    provider = active_provider()
    if not provider:
        return {"ok": False, "name": "codex",
                "error": "no API key configured yet - run: councilkey setup",
                "hint": "councilkey setup   (choose OpenAI or OpenRouter, paste the key - stored encrypted)"}

    if provider == "anthropic":
        return {"ok": False, "name": "codex",
                "error": "Codex CLI speaks the OpenAI protocol - it cannot use an Anthropic key directly",
                "hint": "choose OpenAI or OpenRouter in 'councilkey setup', or use Claude Code for Anthropic"}
    if provider == "gemini":
        return {"ok": False, "name": "codex",
                "error": "Codex CLI needs an OpenAI-compatible endpoint - Gemini's API is not compatible",
                "hint": "choose OpenAI or OpenRouter in 'councilkey setup', or use the Gemini CLI for Gemini keys"}

    config_path = Path(os.environ.get("CODECONFIG", Path.home() / ".codex" / "config.toml"))
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if provider == "openai":
            # Codex's built-in default provider IS OpenAI - only the key env
            # var is needed. Write a minimal config so nothing is ambiguous.
            content = (
                "# written by councilkey - provider: openai (Codex's default)\n"
                'model_reasoning_effort = "high"\n'
            )
            config_path.write_text(content, encoding="utf-8")
            return {"ok": True, "name": "codex",
                    "detail": f"config written: {config_path} (provider: openai - no base URL needed)",
                    "next": "run: codex   (OPENAI_API_KEY is loaded from the vault when you launch)"}
        # provider == "openrouter" (officially documented by OpenRouter)
        content = (
            "# written by councilkey - provider: openrouter\n"
            '# change the model anytime (any OpenRouter model that supports the Responses API)\n'
            'model = "openai/gpt-5.3-codex"\n'
            'model_provider = "openrouter"\n'
            'model_reasoning_effort = "high"\n\n'
            "[model_providers.openrouter]\n"
            'name = "OpenRouter"\n'
            'base_url = "https://openrouter.ai/api/v1"\n'
            'env_key = "OPENROUTER_API_KEY"\n'
            'wire_api = "responses"\n'
        )
        config_path.write_text(content, encoding="utf-8")
        return {"ok": True, "name": "codex",
                "detail": f"config written: {config_path} (provider: openrouter, model: openai/gpt-5.3-codex)",
                "next": "run: codex   (OPENROUTER_API_KEY is loaded from the vault when you launch)"}
    except Exception as exc:
        return {"ok": False, "name": "codex",
                "error": f"could not write the Codex config at {config_path}: {exc}",
                "hint": "make sure the folder is writable, then re-run: councilkey agents configure codex"}


def openclaw_local_command() -> str:
    """The one-shot command that makes an installed OpenClaw answer using the
    same local Ollama model as the council - with a placeholder for the message."""
    return "openclaw agent -m \"<your question>\" --local --agent main --model ollama/qwen2.5:3b"
