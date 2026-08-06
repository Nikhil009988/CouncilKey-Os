"""Cross-platform command execution helpers.

On Windows, executables like `npm`, `pip` are `npm.cmd` / `pip.exe` —
calling them by bare name through subprocess without a shell raises
[WinError 2] "The system cannot find the file specified". This module
resolves the real executable (including PATHEXT suffixes) so installers
work identically on Windows, Linux and macOS.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def which_resolved(cmd: str) -> str | None:
    """Like shutil.which, but also tries PATHEXT suffixes (npm -> npm.cmd)."""
    found = shutil.which(cmd)
    if found:
        return found
    if os.name == "nt":
        pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";")
        for ext in pathext:
            cand = shutil.which(cmd + ext.lower()) or shutil.which(cmd + ext)
            if cand:
                return cand
    return None


def resolve_cmd(cmd: str) -> str:
    """Return the runnable path for a command name (falls back to the name)."""
    return which_resolved(cmd) or cmd


def run_cmd(
    args: list[str],
    cwd: Path | str | None = None,
    timeout: int = 900,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Run a command cross-platform. Returns (ok, tail-of-output).

    - resolves the executable (Windows .cmd/.exe handling)
    - passes environment overrides (e.g. PATH)
    - captures stdout+stderr and returns the tail
    """
    cmd = list(args)
    cmd[0] = resolve_cmd(cmd[0])
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
            env=full_env,
        )
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-600:]
        return proc.returncode == 0, tail.strip()
    except Exception as exc:
        return False, str(exc)
