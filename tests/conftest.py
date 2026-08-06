"""Pytest bootstrap: keep all tests inside an isolated council home.

Imported by pytest before any test module, so module-level side effects
(like JOURNAL_DIR.mkdir in council.orchestrator.main) never touch the real
/var/lib/council on developer or CI machines.
"""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="council-test-")
os.environ["COUNCIL_HOME"] = _TMP
# Point Ollama at a dead port so network probes fail fast instead of hanging.
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:9")


def cli_path():
    """Path to the councilkey console script (venv Scripts on Windows)."""
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "councilkey.exe"
    return root / ".venv" / "bin" / "councilkey"
