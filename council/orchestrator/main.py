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
from pydantic import BaseModel

from council.orchestrator.agents import AgentResult, build_default_clients

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
JOURNAL_DIR = COUNCIL_HOME / "journal"
JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="CouncilKey-Os", version="1.0.0")
clients: dict[str, Any] = {}


class AskRequest(BaseModel):
    prompt: str
    strategy: str = "majority"
    min_agreement: int = 2


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
    tasks = [agents[k].ask(req.prompt) for k in agents]
    responses: list[AgentResult] = await asyncio.gather(*tasks)
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
    return HTMLResponse(
        "<html><body><h1>CouncilKey-Os</h1><p>Use <a href='/docs'>/docs</a> or connect WS at /ws</p></body></html>"
    )


def cli_dashboard(port: int = 8000, host: str = "0.0.0.0") -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli_dashboard()
