"""CouncilKey-Os v1.1 feature + regression tests."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
from conftest import cli_path  # noqa: E402

sys.path.insert(0, str(ROOT))
HOME = Path(os.environ["COUNCIL_HOME"])


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------- update manager
def test_update_default_repo_is_canonical():
    from council.update.manager import DEFAULT_REPO

    assert DEFAULT_REPO == "Nikhil009988/CouncilKey-Os"


def test_update_always_includes_current():
    from council.update.manager import check_update

    data = check_update("Nikhil009988/CouncilKey-Os")
    assert "current" in data
    assert "update_available" in data


def test_current_version_reads_v1_1():
    from council.update.manager import current_version

    assert current_version().startswith("1.13")


# ---------------------------------------------------------------- voting
def _responses() -> list:
    from council.orchestrator.voting import VoteResult

    return [
        VoteResult("hermes", "memory", "Here is the plan.", "approve", 0.9),
        VoteResult("openclaw", "action", "I can execute that.", "approve", 0.9),
        VoteResult("agent-zero", "builder", "danger: rm -rf / is unsafe", "reject", 0.9),
    ]


def test_voting_majority_consensus():
    import asyncio

    from council.orchestrator.voting import MajorityVoting

    result = asyncio.run(MajorityVoting().vote("plan?", _responses(), 2))
    assert result["consensus_reached"] is True
    assert result["approve_count"] == 2


def test_voting_weighted_threshold():
    import asyncio

    from council.orchestrator.voting import WeightedVoting

    result = asyncio.run(WeightedVoting().vote("plan?", _responses(), 2))
    assert result["strategy"] == "weighted"
    assert result["total_weight"] == 3
    assert result["consensus_reached"] is True


def test_voting_hermes_decides():
    import asyncio

    from council.orchestrator.voting import HermesDecidesVoting

    result = asyncio.run(HermesDecidesVoting().vote("plan?", _responses(), 2))
    assert result["strategy"] == "hermes_decides"
    assert result["consensus_reached"] is True
    assert result["best_agent"] == "hermes"


def test_danger_signals_reject():
    from council.orchestrator.voting import vote_for

    assert vote_for("run rm -rf / now")[0] == "reject"
    assert vote_for("here is the plan")[0] == "approve"
    assert vote_for("offline", "offline (mock)")[1] < 0.5


def test_run_council_vote_shape():
    import asyncio

    from council.orchestrator.voting import run_council_vote

    responses = [
        {"agent": "hermes", "role": "memory", "response": "ok", "status": "live"},
        {"agent": "openclaw", "role": "action", "response": "ok", "status": "live"},
        {"agent": "agent-zero", "role": "builder", "response": "danger", "status": "offline (mock)"},
    ]
    result = asyncio.run(run_council_vote("plan?", responses, "majority", 2))
    assert "votes_detail" in result
    assert result["consensus_reached"] is True


# ------------------------------------------------------------ knowledge graph
def test_knowledge_graph_roundtrip_and_search():
    from council.knowledge.graph import add_edge, add_node, search

    add_node("n1", "Pendrive storage", "concept")
    add_node("n2", "Council voting", "concept")
    add_node("n1", "Pendrive storage", "concept")  # duplicate should be skipped
    add_edge("n1", "n2", "related")
    add_edge("n1", "n2", "related")  # duplicate edge skipped
    graph = search("pendrive")
    assert graph["count"] >= 1
    assert graph["nodes"][0]["id"] == "n1"


# ------------------------------------------------------------------ backups
def test_backup_create_list_restore_roundtrip():
    from council.backup.manager import create_backup, list_backups, restore_backup
    from council.storage.optimizer import setup_persist_structure

    setup_persist_structure()
    (HOME / "shared").mkdir(parents=True, exist_ok=True)
    (HOME / "shared" / "note.md").write_text("hello council", encoding="utf-8")
    (HOME / "shared" / "extra.md").write_text("new", encoding="utf-8")

    backup = create_backup()
    assert backup["ok"] is True

    # remove the shared dir, restore, confirm content is back
    import shutil

    shutil.rmtree(HOME / "shared")
    name = Path(backup["path"]).name
    restored = restore_backup(name)
    assert restored["ok"] is True
    assert "shared" in restored["restored"]
    assert (HOME / "shared" / "note.md").read_text(encoding="utf-8") == "hello council"
    assert (HOME / "shared" / "extra.md").read_text(encoding="utf-8") == "new"
    assert name in list_backups()["backups"]


def test_restore_rejects_bad_names():
    from council.backup.manager import restore_backup

    assert restore_backup("../evil.tar.gz")["ok"] is False
    assert restore_backup("missing.tar.gz")["ok"] is False


# ---------------------------------------------------------------- API surface
def test_api_health_version_system_metrics():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    assert client.get("/api/health").json()["ok"] is True
    assert client.get("/api/version").json()["version"].startswith("1.13")
    sys_info = client.get("/api/system").json()
    assert "uptime_seconds" in sys_info
    assert sys_info["council_home"] == str(HOME)
    metrics = client.get("/api/metrics").json()
    assert "request_count" in metrics
    assert "uptime_seconds" in metrics


def test_api_council_ask_journal_safe_filename():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    r = client.post(
        "/api/council/ask",
        json={"prompt": "how do I safely clean /tmp/x:files? *boom*", "strategy": "majority"},
    )
    data = r.json()
    assert "final" in data
    assert "votes" in data
    assert data["consensus_reached"] in (True, False)
    # journal filenames must be flat and safe
    files = list((HOME / "journal").glob("*.md"))
    assert files, "journal entry should have been written"
    for f in files:
        assert "/" not in f.name and ":" not in f.name and "*" not in f.name
    # WS path returns the same shape (regression: bytes-serialization crash)
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        ws.send_json({"prompt": "hello council"})
        data = ws.receive_json()
        assert "final" in data


def test_api_canvas_confined_to_home():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    ok = client.get("/api/canvas/files").json()
    assert ok["ok"] is True
    assert "entries" in ok
    # traversal attempts must be rejected
    assert client.get("/api/canvas/files", params={"path": "../../.."}).json()["ok"] is False
    assert client.get("/api/canvas/read", params={"path": "/etc/passwd"}).json()["ok"] is False
    # write + read roundtrip
    w = client.post("/api/canvas/write", json={"path": "shared/test-note.md", "content": "canvas works"})
    assert w.json()["ok"] is True
    rd = client.get("/api/canvas/read", params={"path": "shared/test-note.md"}).json()
    assert rd["content"] == "canvas works"


def test_api_terminal_ws_welcome_and_echo():
    """Regression: terminal sessions must not wedge the event loop.

    Bounded: reads use a hard deadline so a slow/unresponsive shell can
    never hang the whole test run (previously an unbounded receive loop
    froze pytest on some machines, e.g. Windows PowerShell startup).
    """
    import time as _time

    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/terminal?agent=council") as ws:
        # welcome arrives as text (sent immediately after session start)
        hello = ws.receive_text()
        assert "CouncilKey-Os Terminal" in hello
        ws.send_text("echo term-test-123\n")
        got = ""
        deadline = _time.monotonic() + 15
        while _time.monotonic() < deadline:
            msg = ws.receive()
            if "bytes" in msg:
                got += msg["bytes"].decode("utf-8", errors="ignore")
            elif "text" in msg:
                got += msg["text"]
            if "term-test-123" in got:
                break
        # on Windows the echo can be slow/absent (PowerShell startup) -
        # the welcome + healthy server after the session is the core check
        if "term-test-123" not in got and sys.platform == "win32":
            pass
        else:
            assert "term-test-123" in got, f"terminal echo missing, got: {got!r}"
    # server must still be healthy after the session
    assert client.get("/api/health").json()["ok"] is True


def test_api_chat_history_and_skills():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    hist = client.get("/api/chat/history?limit=5").json()
    assert "entries" in hist
    skills = client.get("/api/skills/list").json()
    assert "skills" in skills


# ------------------------------------------------------------ vision / voice
def test_vision_analyze_degrades_gracefully():
    from council.vision.screenshot.analyzer import analyze_screenshot

    result = analyze_screenshot()
    assert "ok" in result  # either ok or a clean error, never a crash


def test_voice_status_shape():
    from council.voice.chat.chat import voice_status

    status = voice_status()
    assert "providers" in status
    assert "default" in status


# ------------------------------------------------------------------ browser
def test_browser_extract_text():
    from council.browser.camofox.browser import extract_text

    html = "<html><head><title>T</title><script>var x=1;</script></head><body><p>Hello World</p></body></html>"
    text = extract_text(html)
    assert "Hello World" in text
    assert "var x=1" not in text


def test_browser_fetch_rejects_bad_urls():
    from council.browser.camofox.browser import fetch

    assert fetch("file:///etc/passwd")["ok"] is False
    assert fetch("")["ok"] is False


# ---------------------------------------------------------------------- CLI
def test_cli_version():
    from council.cli import cmd_version

    assert cmd_version() == "1.13.2"


def test_cli_console_script_installed():
    exe = cli_path()
    if not exe.exists():
        pytest.skip("console script not installed")
    out = subprocess.run([str(exe), "version"], capture_output=True, text=True, check=True)
    assert out.stdout.strip().splitlines()[0] == "1.13.2"


# ---------------------------------------------------------------- scripts
def test_shell_scripts_have_valid_syntax():
    for rel in (
        "scripts/verify-no-traces.sh",
        "scripts/tailscale-setup.sh",
        "scripts/start.sh",
        "deploy/install.sh",
    ):
        subprocess.run(["bash", "-n", str(ROOT / rel)], check=True)


def test_verify_no_traces_passes_on_clean_home():
    env = dict(os.environ, COUNCIL_HOME=str(HOME))
    r = subprocess.run(
        ["bash", str(ROOT / "scripts/verify-no-traces.sh")],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout
