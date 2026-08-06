"""CouncilKey-Os v1.2 - advanced orchestration & intelligence tests."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
HOME = Path(os.environ["COUNCIL_HOME"])


# ------------------------------------------------------------- decomposition
def test_decompose_prompt_structure():
    from council.orchestrator.decomposer import decompose_prompt

    subtasks = decompose_prompt("build a website")
    assert len(subtasks) == 3
    assert [s["id"] for s in subtasks] == ["analysis", "execution", "review"]
    assert all(s["agent"] in ("hermes", "openclaw", "agent-zero") for s in subtasks)


def test_run_decomposed():
    from council.orchestrator.decomposer import run_decomposed

    result = asyncio.run(run_decomposed("plan a weekend trip", "majority", 2))
    assert result["mode"] == "decomposed"
    assert len(result["subtasks"]) == 3
    assert "final" in result
    assert result["consensus_reached"] in (True, False)
    assert result["votes"]


# ------------------------------------------------------------------- debate
def test_run_debate():
    from council.orchestrator.debate import run_debate

    result = asyncio.run(run_debate("should we use sqlite or postgres", rounds=3, strategy="majority", min_agreement=2))
    assert result["mode"] == "debate"
    assert result["rounds"] >= 1
    assert result["rounds"] <= 3
    assert len(result["rounds_log"]) == result["rounds"]
    assert "final" in result


# ------------------------------------------------------------ semantic cache
def test_semantic_cache_roundtrip():
    from council.cache.semantic import flush, get, put, stats

    flush()
    put("key-1", {"final": "cached answer", "votes": {"hermes": "approve"}})
    cached = get("key-1", ttl=60)
    assert cached == {"final": "cached answer", "votes": {"hermes": "approve"}}
    assert get("key-missing") is None
    assert get("key-1", ttl=-1) is None  # expired
    s = stats()
    assert s["entries"] == 1
    flush()
    assert stats()["entries"] == 0


# -------------------------------------------------------------------- tfidf
def test_tfidf_build_and_search():
    from council.search.tfidf import build_index, search

    (HOME / "journal").mkdir(parents=True, exist_ok=True)
    (HOME / "journal" / "2026-08-05-000000-test.md").write_text(
        "The quick brown fox jumps over the lazy dog.\n", encoding="utf-8"
    )
    (HOME / "journal" / "2026-08-05-000001-other.md").write_text(
        "Council voting requires majority consensus among agents.\n", encoding="utf-8"
    )
    built = build_index()
    assert built["ok"] is True
    assert built["doc_count"] >= 2

    result = search("fox")
    assert result["ok"] is True
    assert result["total"] >= 1
    assert result["results"][0]["file"].endswith("test.md")

    result2 = search("voting consensus")
    assert result2["total"] >= 1
    assert result2["results"][0]["file"].endswith("other.md")


# --------------------------------------------------------------- task queue
def test_task_queue_lifecycle():
    from council.scheduler.queue import TaskQueue

    async def scenario():
        q = TaskQueue()

        async def echo(payload):
            await asyncio.sleep(0.05)
            return {"echo": payload["prompt"]}

        q.register_handler("echo", echo)
        first = await q.enqueue("echo", {"prompt": "hello"}, priority=5)
        second = await q.enqueue("echo", {"prompt": "bye"}, priority=1)
        cancelled = await q.enqueue("echo", {"prompt": "never"}, priority=9)
        await q.cancel(cancelled) is True

        asyncio.create_task(q.run())
        await asyncio.sleep(0.6)
        await q.stop()
        return q, first, second, cancelled

    q, first, second, cancelled = asyncio.run(scenario())
    done = asyncio.run(q.get(first))
    assert done["status"] == "done"
    assert done["result"]["echo"] == "hello"
    assert asyncio.run(q.get(second))["status"] == "done"
    assert asyncio.run(q.get(cancelled))["status"] == "cancelled"
    assert q.stats()["processed"] == 2
    assert len(asyncio.run(q.list())) == 3


# -------------------------------------------------------------------- audit
def test_audit_record_recent_stats():
    from council.tracing.audit import recent, record, stats

    record({"id": "a1", "mode": "council", "strategy": "majority", "consensus": True, "duration_ms": 12.5,
            "agents": [{"agent": "hermes", "status": "live", "latency": 0.3}]})
    record({"id": "a2", "mode": "debate", "strategy": "majority", "consensus": False, "duration_ms": 8.0,
            "agents": [{"agent": "openclaw", "status": "offline (mock)", "latency": 0.0}]})

    entries = recent(limit=10)
    assert len(entries) >= 2
    assert entries[-1]["id"] == "a2"

    s = stats()
    assert s["total"] >= 2
    assert 0 <= s["consensus_rate"] <= 1
    assert s["avg_duration_ms"] > 0
    assert s["by_agent"]["hermes"]["live"] >= 1
    assert s["by_agent"]["openclaw"]["mock"] >= 1


# ------------------------------------------------------------------- vault
def test_vault_roundtrip_no_plaintext():
    from council.secrets.vault import delete_secret, list_secrets, set_secret, vault_status

    set_secret("TEST_KEY", "super-secret-value-123")
    info = list_secrets()
    assert "TEST_KEY" in info["keys"]
    assert "backend" in info

    from council.secrets.vault import get_secret

    assert get_secret("TEST_KEY") == "super-secret-value-123"

    # plaintext must not appear in the vault file
    vault_file = HOME / "secrets" / "vault.json"
    assert vault_file.exists()
    raw = vault_file.read_text(encoding="utf-8")
    assert "super-secret-value-123" not in raw

    delete_secret("TEST_KEY")
    assert "TEST_KEY" not in list_secrets()["keys"]
    assert vault_status()["ok"] is True


# ----------------------------------------------------------- terminal guard
def test_terminal_guard():
    from council.terminal.guard import check_command, strip_ansi

    allowed, _ = check_command("echo hello")
    assert allowed is True
    allowed, _ = check_command("ls -la /tmp")
    assert allowed is True

    blocked, reason = check_command("rm -rf /")
    assert blocked is False and "delete" in reason
    blocked, _ = check_command("mkfs.ext4 /dev/sdb1")
    assert blocked is False
    blocked, _ = check_command("dd if=/dev/zero of=/dev/sda bs=1M")
    assert blocked is False
    blocked, _ = check_command("shutdown -h now")
    assert blocked is False
    blocked, _ = check_command(":(){ :|:& };:")
    assert blocked is False

    # force prefix and allowlist bypass
    allowed, _ = check_command("!force rm -rf /")
    assert allowed is True

    # ansi stripping
    assert strip_ansi("\x1b[1;32mhi\x1b[0m") == "hi"


# --------------------------------------------------------------- retrieval
def test_retrieve_context_finds_journal():
    from council.memory.retrieval import retrieve_context

    (HOME / "journal").mkdir(parents=True, exist_ok=True)
    # filename sorts LAST so it stays in the retrieval window even after
    # other tests add many journal entries (history() takes the newest 30)
    (HOME / "journal" / "9999-12-31-235959-storage.md").write_text(
        "# Council Journal 9999-12-31-235959\n\n## Prompt\nstorage optimization tips\n\n## Final\n"
        "Use keep/cache split and delete raw sessions.\n",
        encoding="utf-8",
    )
    context = retrieve_context("how should I optimize storage", top_k=2)
    assert isinstance(context, str)
    assert "storage" in context.lower()


# -------------------------------------------------------------------- APIs
def test_api_tasks_secrets_search():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)

    # tasks
    r = client.post("/api/tasks", json={"kind": "ask", "prompt": "ping", "priority": 3})
    assert r.json()["ok"] is True
    task_id = r.json()["id"]
    listed = client.get("/api/tasks").json()
    assert any(t["id"] == task_id for t in listed["tasks"])
    detail = client.get(f"/api/tasks/{task_id}").json()
    assert detail["kind"] == "ask"

    # secrets
    assert client.post("/api/secrets", json={"key": "API_TOKEN", "value": "abc123"}).json()["ok"] is True
    assert "API_TOKEN" in client.get("/api/secrets").json()["keys"]
    masked = client.get("/api/secrets/API_TOKEN").json()
    assert masked["masked"] == "ab**23"
    assert client.delete("/api/secrets/API_TOKEN").json()["ok"] is True

    # search index + query
    assert client.post("/api/search/index").json()["ok"] is True
    res = client.get("/api/search", params={"q": "storage"}).json()
    assert res["ok"] is True
    assert "results" in res

    # cache endpoints
    stats = client.get("/api/cache/stats").json()
    assert "hits" in stats
    assert client.post("/api/cache/flush").json()["ok"] is True

    # audit endpoints
    assert client.get("/api/audit").json() is not None
    assert "total" in client.get("/api/audit/stats").json()


def test_api_sse_stream():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/council/ask/stream",
        json={"prompt": "stream test prompt", "strategy": "majority"},
    ) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        body = "".join(r.iter_text())
    assert "data: " in body
    assert '"event": "start"' in body
    assert '"event": "done"' in body
    assert "Council Decision" in body


def test_api_decompose_debate():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    dec = client.post("/api/council/decompose", json={"prompt": "plan a product launch"}).json()
    assert dec["mode"] == "decomposed"
    assert len(dec["subtasks"]) == 3

    deb = client.post("/api/council/debate", json={"prompt": "sqlite vs postgres", "rounds": 2}).json()
    assert deb["mode"] == "debate"
    assert deb["rounds"] <= 2
