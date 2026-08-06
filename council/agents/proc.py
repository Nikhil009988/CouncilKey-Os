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
from typing import Any


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
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return proc.returncode == 0, out
    except Exception as exc:
        return False, str(exc)


def run_with_progress(
    fn: Any,
    label: str,
    interval: float = 5.0,
) -> Any:
    """Run fn() while showing a live elapsed-time progress line.

    The line updates every `interval` seconds (e.g. "⏳ installing
    openclaw... 12s elapsed (please wait)") and is cleared when fn returns,
    so the user always knows the wizard is alive and what it is doing.

    fn is expected to block (e.g. a subprocess call).
    """
    import threading
    import time as _time

    done = threading.Event()
    start = _time.monotonic()
    result: dict[str, Any] = {"value": None, "error": None}

    def _tick() -> None:
        while not done.is_set():
            elapsed = int(_time.monotonic() - start)
            print(f"\r  ⏳ {label}... {elapsed}s elapsed (please wait)", end="", flush=True)
            done.wait(interval)
        print("\r" + " " * 70 + "\r", end="", flush=True)

    ticker = threading.Thread(target=_tick, daemon=True)
    ticker.start()
    try:
        result["value"] = fn()
    except Exception as exc:  # pragma: no cover - surfaced to the caller
        result["error"] = exc
    finally:
        done.set()
        ticker.join(timeout=2)
    if result["error"] is not None:
        raise result["error"]
    return result["value"]


def human_duration(seconds: float) -> str:
    """Format seconds as '45s' or '2m 10s'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m {seconds % 60:02d}s"
