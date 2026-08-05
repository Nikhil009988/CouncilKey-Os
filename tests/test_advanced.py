"""CouncilKey-Os advanced tests."""
from __future__ import annotations

import importlib.util
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


def test_config_defaults():
    mod = _load("config", "council/config/loader.py")
    data = mod.load()
    assert data["council"]["mode"] == "debate"
    assert data["council"]["consensus"]["strategy"] == "majority"


def test_lancedb_add_search_no_deps():
    mod = _load("lancedb", "council/embeddings/lancedb.py")
    try:
        res = mod.add_documents(["hello world", "build website"])
    except RuntimeError:
        pytest.skip("lancedb not installed")
        return
    # Handle case where table already exists from previous test run
    if not res.get("ok") and "already exists" in res.get("error", ""):
        # Table exists, try search directly
        s = mod.search("hello")
        assert "results" in s
        return
    assert res.get("ok") is True
    s = mod.search("hello")
    assert "results" in s


def test_ollama_status_offline():
    mod = _load("ollama", "council/llm/ollama.py")
    data = mod.is_running()
    assert "running" in data


def test_update_check_shape():
    mod = _load("update", "council/update/manager.py")
    data = mod.check_update("nikhilgundu99/CouncilKey-Os")
    assert "update_available" in data
    if data.get("update_available"):
        assert "latest" in data
    assert "current" in data or data.get("status") == 404


def test_metrics_snapshot_shape():
    mod = _load("metrics", "council/metrics/snapshot.py")
    data = mod.snapshot()
    assert "cpu_percent" in data
    assert "memory_percent" in data
    assert "storage_bytes" in data
