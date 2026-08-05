"""CouncilKey-Os tests."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_storage_audit():
    mod = _load("storage_optimizer", "council/storage/optimizer.py")
    result = mod.audit()
    assert "total_keep" in result
    assert result["total_keep"] >= 0


def test_storage_optimize_noop():
    mod = _load("storage_optimizer", "council/storage/optimizer.py")
    result = mod.optimize(dry_run=True)
    assert result["dry_run"] is True


def test_storage_setup():
    mod = _load("storage_optimizer", "council/storage/optimizer.py")
    result = mod.setup_persist_structure()
    assert result["ok"] is True


def test_journal_analyze_empty():
    os_env = {"COUNCIL_HOME": str(ROOT / "tests/fixtures/council_home")}
    import council.journal.analyzer as analyzer
    old = os.environ.get("COUNCIL_HOME")
    os.environ["COUNCIL_HOME"] = os_env["COUNCIL_HOME"]
    try:
        res = analyzer.analyze()
        assert "total_entries" in res
    finally:
        if old is None:
            os.environ.pop("COUNCIL_HOME", None)
        else:
            os.environ["COUNCIL_HOME"] = old


def test_agents_mock():
    from council.orchestrator import agents as mod
    clients = mod.build_default_clients()
    assert set(clients.keys()) == {"hermes", "openclaw", "agent-zero"}
