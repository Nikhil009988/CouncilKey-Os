"""CouncilKey-Os v1.3 - agent installer tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_agents_installer_known_agents():
    from council.agents.installer import AGENTS

    assert set(AGENTS) == {"hermes", "openclaw", "agent-zero", "crewai", "aider"}
    # each agent documents its official install method
    assert AGENTS["hermes"]["install"] == "official-installer"
    assert AGENTS["openclaw"]["install"] == "npm"
    assert AGENTS["agent-zero"]["install"] == "docker-launcher"
    assert AGENTS["crewai"]["install"] == "pip"
    assert AGENTS["aider"]["install"] == "pip"
    # official URLs/commands are present
    assert AGENTS["hermes"]["installer_url"].startswith("https://")
    assert AGENTS["openclaw"]["package"] == "openclaw@latest"
    assert AGENTS["crewai"]["package"] == "crewai"
    assert AGENTS["aider"]["package"] == "aider-chat"


def test_agents_status_shape():
    from council.agents.installer import status

    data = status()
    assert set(data) == {"hermes", "openclaw", "agent-zero", "crewai", "aider"}
    for name, info in data.items():
        assert "installed" in info
        assert "binary" in info
        assert "install" in info
        assert info["state"] in ("installed", "not installed")


def test_agents_install_unknown_name():
    from council.agents.installer import install

    result = install("nope")
    assert result["ok"] is False
    assert "unknown agent" in result["error"]


def test_agents_prereqs_shape():
    from council.agents.installer import check_prereqs

    prereqs = check_prereqs()
    assert isinstance(prereqs, dict)
    assert "git" in prereqs
    assert "node" in prereqs
    assert "npm" in prereqs
    assert "docker" in prereqs
    assert "curl" in prereqs


def test_api_agents_prereqs():
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    client = TestClient(app)
    data = client.get("/api/agents/prereqs").json()
    assert "git" in data
    assert "docker" in data


def test_api_task_install_agent_unknown():
    """The install_agent task kind exists and handles bad names cleanly."""
    from fastapi.testclient import TestClient

    from council.orchestrator.main import app

    # `with` runs the lifespan so the queue worker is actually started
    with TestClient(app) as client:
        r = client.post("/api/tasks", json={"kind": "install_agent", "name": "nope"})
        assert r.json()["ok"] is True
        task_id = r.json()["id"]

        import time

        for _ in range(20):
            task = client.get(f"/api/tasks/{task_id}").json()
            if task["status"] in ("done", "failed"):
                break
            time.sleep(0.2)
    assert task["status"] in ("done", "failed")
    result = task.get("result") or {}
    assert result.get("ok") is False
    assert "unknown agent" in result.get("error", "")


def test_setup_script_syntax():
    import subprocess

    for rel in ("scripts/setup.sh", "install.sh"):
        subprocess.run(["bash", "-n", str(ROOT / rel)], check=True)
