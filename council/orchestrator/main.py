#!/usr/bin/env python3
"""CouncilKey-Os Council Core - FastAPI + WebSocket orchestrator."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from council.orchestrator.agents import AgentResult, build_default_clients

from council.config.loader import load as config_load, save as config_save
from council.embeddings.lancedb import add_documents as lancedb_add, search as lancedb_search
from council.llm.ollama import chat as ollama_chat, embeddings as ollama_embeddings, is_running as ollama_running
from council.journal.analyzer import analyze as journal_analyze, list_journal
from council.backup.manager import create_backup as backup_create, list_backups as backup_list
from council.llm.manager import available as llm_available
from council.memory.consolidation import nightly_consolidate
from council.network.tailscale import tailscale_status, setup_tailscale
from council.reflection.self import reflect_on_last
from council.skills.evolution import evolve

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
JOURNAL_DIR = COUNCIL_HOME / "journal"
JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="CouncilKey-Os", version="1.0.0")
clients: dict[str, Any] = {}

_dashboard_html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


class AskRequest(BaseModel):
    prompt: str
    strategy: str = "majority"
    min_agreement: int = 2
    mode: str = "together"
    agent: str | None = None


class OptimizeRequest(BaseModel):
    dry_run: bool = False


def _safe(s: str) -> str:
    return s.replace("<", "&lt;").replace(">", "&gt;")


def _append_journal(prompt: str, result: dict[str, Any]) -> Path:
    ts = time.strftime("%Y-%m-%d-%H%M%S")
    slug = _safe(prompt)[:40].replace(" ", "-")
    path = JOURNAL_DIR / f"{ts}-{slug}.md"
    path.write_text(
        f"# Council Journal {ts}\n\n## Prompt\n{prompt}\n\n## Strategy\n{result.get('strategy')}\n\n## Votes\n{result.get('votes')}\n\n## Final\n{result.get('final')}\n",
        encoding="utf-8",
    )
    return path


@app.get("/api/status")
def status() -> JSONResponse:
    return JSONResponse(
        {
            "agents": {
                "hermes": {"status": "online", "role": "memory", "port": 18790},
                "openclaw": {"status": "online", "role": "action", "port": 18789},
                "agent-zero": {"status": "online", "role": "builder", "port": 50001},
            },
            "council": {"mode": "debate", "consensus": {"strategy": "majority"}},
            "journal": [
                {"file": p.name, "size": p.stat().st_size}
                for p in sorted(JOURNAL_DIR.glob("*.md"))[-20:]
            ],
        }
    )


@app.post("/api/council/ask")
async def ask(req: AskRequest) -> JSONResponse:
    agents = build_default_clients()
    if req.mode == "alone" and req.agent and req.agent in agents:
        responses: list[AgentResult] = [await agents[req.agent].ask(req.prompt)]
    else:
        responses = await asyncio.gather(*[agents[k].ask(req.prompt) for k in agents])
    votes = {r.agent: ("approve" if "danger" not in r.response.lower() else "reject") for r in responses}
    approve = sum(1 for v in votes.values() if v == "approve")
    consensus = approve >= req.min_agreement
    best = max(responses, key=lambda r: len(r.response))
    final = "\n\n".join(
        f"## {r.agent} ({r.role})\n{r.response}\n_Status: {r.status}, latency: {r.latency:.2f}s_"
        for r in responses
    )
    if consensus:
        final = f"# Council Decision - Consensus {approve}/{len(responses)} ✅\n\n" + final
    else:
        final = f"# Council Decision - No Consensus {approve}/{len(responses)} ❌\n\n" + final
    result = {
        "strategy": req.strategy,
        "votes": votes,
        "approve_count": approve,
        "consensus_reached": consensus,
        "best_agent": best.agent,
        "final": final,
        "responses": [
            {
                "agent": r.agent,
                "role": r.role,
                "response": r.response,
                "latency": round(r.latency, 2),
                "status": r.status,
            }
            for r in responses
        ],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _append_journal(req.prompt, result)
    return JSONResponse(result)


@app.websocket("/ws")
async def ws(ws: WebSocket) -> None:
    await ws.accept()
    await ws.send_json({"type": "hello", "msg": "CouncilKey-Os v2 Dashboard WS connected - 3 agents live"})
    try:
        while True:
            data = await ws.receive_json()
            prompt = data.get("prompt", "")
            if not prompt:
                continue
            req = AskRequest(prompt=prompt, strategy=data.get("strategy", "majority"))
            result = await ask(req)
            await ws.send_json(result.body)
    except WebSocketDisconnect:
        pass


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(_dashboard_html)


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.get("/api/journal")
def journal() -> JSONResponse:
    return JSONResponse(list_journal())


@app.get("/api/journal/analyze")
def journal_analyze_route() -> JSONResponse:
    return JSONResponse(journal_analyze())


@app.get("/api/storage/audit")
def storage_audit() -> JSONResponse:
    from council.storage.optimizer import audit as audit_fn
    return JSONResponse(audit_fn())


@app.get("/api/storage/what-if")
def storage_whatif() -> JSONResponse:
    from council.storage.optimizer import what_if_delete as whatif_fn
    return JSONResponse(whatif_fn())


@app.post("/api/storage/optimize")
def storage_optimize(req: OptimizeRequest) -> JSONResponse:
    from council.storage.optimizer import optimize as optimize_fn
    return JSONResponse(optimize_fn(dry_run=req.dry_run))


@app.post("/api/storage/setup")
def storage_setup() -> JSONResponse:
    from council.storage.optimizer import setup_persist_structure as setup_fn
    return JSONResponse(setup_fn())


@app.get("/api/backup/list")
def backup_list_route() -> JSONResponse:
    return JSONResponse(backup_list())


@app.post("/api/backup/create")
def backup_create_route() -> JSONResponse:
    return JSONResponse(backup_create())


@app.get("/api/llm/available")
def llm_available_route() -> JSONResponse:
    return JSONResponse(llm_available())


@app.get("/api/network/tailscale")
def tailscale_status_route() -> JSONResponse:
    return JSONResponse(tailscale_status())


@app.post("/api/network/tailscale/setup")
def tailscale_setup_route() -> JSONResponse:
    return JSONResponse(setup_tailscale())


@app.get("/api/reflection/last")
def reflection_last_route() -> JSONResponse:
    return JSONResponse(reflect_on_last())


@app.post("/api/skills/evolve")
def skills_evolve_route() -> JSONResponse:
    return JSONResponse(evolve())


@app.get("/api/config")
def config_route() -> JSONResponse:
    return JSONResponse(config_load())


@app.post("/api/config")
def config_save_route(body: dict[str, object]) -> JSONResponse:
    config_save(body)
    return JSONResponse({"ok": True})


@app.get("/api/embeddings/search")
def embeddings_search(q: str = "", limit: int = 5) -> JSONResponse:
    if not q:
        return JSONResponse({"ok": True, "results": []})
    return JSONResponse(lancedb_search(q, limit=min(limit, 50)))


@app.post("/api/embeddings/add")
def embeddings_add(body: dict[str, object]) -> JSONResponse:
    docs = body.get("docs", [])
    if not isinstance(docs, list):
        docs = [str(docs)]
    return JSONResponse(lancedb_add([str(x) for x in docs]))


@app.get("/api/ollama/status")
def ollama_status_route() -> JSONResponse:
    return JSONResponse(ollama_running())


@app.post("/api/ollama/chat")
def ollama_chat_route(body: dict[str, object]) -> JSONResponse:
    model = str(body.get("model", "qwen2.5:3b"))
    prompt = str(body.get("prompt", ""))
    system = str(body.get("system", ""))
    return JSONResponse(ollama_chat(model, prompt, system))


@app.get("/api/terminal/status")
def terminal_status_route() -> JSONResponse:
    return JSONResponse({"pty": True, "agent": "council"})


@app.get("/api/optional/agents")
def optional_agents_route() -> JSONResponse:
    return JSONResponse({"crewai": False, "microsoft": False, "llm_judge": True})


@app.get("/api/update/check")
def update_check_route() -> JSONResponse:
    from council.update.manager import check_update as update_fn
    return JSONResponse(update_fn())


@app.get("/api/metrics")
def metrics_route() -> JSONResponse:
    from council.metrics.snapshot import snapshot as metrics_fn
    return JSONResponse(metrics_fn())


def cli_dashboard(port: int = 8000, host: str = "0.0.0.0") -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli_dashboard()
