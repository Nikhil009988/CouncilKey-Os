"""Terminal command guard - blocks dangerous commands unless allowlisted or forced.

The guard intercepts complete command lines before they reach the PTY.
- `!force <cmd>` prefix overrides the guard for a single command
- an allowlist file (COUNCIL_HOME/shared/terminal-allowlist.txt, one command
  per line, `#` comments) permanently permits exact commands
"""
from __future__ import annotations

import os
import re
from pathlib import Path

BLOCKED_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+[/~]", "recursive force delete of root/home"),
    (r"rm\s+-rf\s+/\s*$", "recursive force delete of filesystem root"),
    (r"\bmkfs(\.[a-z0-9]+)?\b", "filesystem formatting"),
    (r"\bdd\s+if=.*of=\s*/dev/", "raw write to a device"),
    (r":\(\)\s*\{\s*:\|:&\s*\};:", "fork bomb"),
    (r"\b(shutdown|poweroff|halt)\b", "system shutdown/reboot"),
    (r"\breboot\b", "system reboot"),
    (r"chmod\s+-R\s+777\s+/", "recursive world-writable on root"),
    (r"\bmv\s+/\s+", "moving the root filesystem"),
]

_ALLOWLIST = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")) / "shared" / "terminal-allowlist.txt"
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a terminal line."""
    return _ANSI_RE.sub("", text)


def load_allowlist() -> set[str]:
    try:
        if _ALLOWLIST.exists():
            return {
                line.strip()
                for line in _ALLOWLIST.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip() and not line.strip().startswith("#")
            }
    except Exception:
        pass
    return set()


def check_command(cmd: str) -> tuple[bool, str]:
    """Return (allowed, reason). Blocked commands get a human-readable reason."""
    c = (cmd or "").strip()
    if not c or c.startswith("#"):
        return True, ""
    if c.startswith("!force "):
        return True, "forced via !force prefix"
    if c in load_allowlist():
        return True, "allowlisted"
    for pattern, reason in BLOCKED_PATTERNS:
        if re.search(pattern, c, re.IGNORECASE):
            return False, reason
    return True, ""
