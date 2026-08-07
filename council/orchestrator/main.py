"""CouncilKey-Os Council Core - FastAPI + WebSocket orchestrator (v1.2.0).

v1.2 additions:
- Task decomposition (/api/council/decompose)
- Iterative multi-round debate (/api/council/debate)
- Streaming council responses over SSE (/api/council/ask/stream)
- Async task queue with priorities (/api/tasks*)
- Semantic result cache (/api/cache/*)
- TF-IDF full-text search (/api/search*)
- Audit trail + analytics (/api/audit*)
- Encrypted secrets vault (/api/secrets*)
- Memory injection (RAG-lite) into agent prompts
- Terminal command guard
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from council import __version__
from council.backup.manager import create_backup as backup_create
from council.backup.manager import list_backups as backup_list
from council.backup.manager import restore_backup as backup_restore
from council.cache.semantic import flush as cache_flush
from council.cache.semantic import get as cache_get
from council.cache.semantic import put as cache_put
from council.cache.semantic import stats as cache_stats
from council.config.loader import load as config_load
from council.config.loader import save as config_save
from council.embeddings.lancedb import add_documents as lancedb_add
from council.embeddings.lancedb import search as lancedb_search
from council.journal.analyzer import analyze as journal_analyze
from council.journal.analyzer import history as journal_history
from council.journal.analyzer import list_journal
from council.llm.ollama import chat as ollama_chat
from council.llm.ollama import delete as ollama_delete
from council.llm.ollama import ensure_models as ollama_ensure_models
from council.llm.ollama import get_model_defaults as ollama_get_defaults
from council.llm.ollama import get_model_info as ollama_show
from council.llm.ollama import is_running as ollama_running
from council.llm.ollama import list_models as ollama_list_models
from council.llm.ollama import pull as ollama_pull
from council.memory.consolidation import memory_summary, nightly_consolidate
from council.memory.retrieval import retrieve_context
from council.metrics.snapshot import snapshot as metrics_snapshot
from council.network.tailscale import setup_tailscale, tailscale_status
from council.orchestrator.agents import AgentResult, build_default_clients
from council.orchestrator.debate import run_debate
from council.orchestrator.decomposer import run_decomposed
from council.orchestrator.voting import run_council_vote
from council.reflection.self import reflect_on_last
from council.scheduler.queue import TaskQueue
from council.search.tfidf import build_index as tfidf_build_index
from council.search.tfidf import search as tfidf_search
from council.secrets.vault import delete_secret as vault_delete
from council.secrets.vault import list_secrets as vault_list
from council.secrets.vault import mask_secret as vault_mask
from council.secrets.vault import set_secret as vault_set
from council.secrets.vault import vault_status
from council.skills.evolution import evolve as skills_evolve
from council.skills.evolution import list_skills, read_skill
from council.system.info import collect as system_info
from council.terminal.websocket import terminal_websocket
from council.tracing.audit import recent as audit_recent
from council.tracing.audit import record as audit_record
from council.tracing.audit import stats as audit_stats
from council.update.manager import check_update as update_check

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
JOURNAL_DIR = COUNCIL_HOME / "journal"


app = FastAPI(title="CouncilKey-Os", version=__version__)

# ---------------------------------------------------------------- middleware
_requests = 0
_rate_hits: dict[str, list[float]] = {}
_RATE_LIMIT = int(os.environ.get("COUNCIL_RATE_LIMIT", "0"))  # requests/min/IP, 0 = off
_API_KEY = os.environ.get("COUNCIL_API_KEY", "")
_cache_stats = {"hits": 0, "misses": 0}


@app.middleware("http")
async def log_and_count(request: Request, call_next: Any) -> Any:
    global _requests
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    _requests += 1
    print(
        f"[council] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.0f}ms)",
        flush=True,
    )
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Any:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self)"
    return response


@app.middleware("http")
async def api_key_guard(request: Request, call_next: Any) -> Any:
    if _API_KEY and request.url.path not in ("/", "/api/health"):
        provided = request.headers.get("authorization", "")
        if provided.startswith("Bearer "):
            provided = provided[7:]
        elif request.query_params.get("token"):
            provided = request.query_params["token"]
        if provided != _API_KEY:
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def rate_limit(request: Request, call_next: Any) -> Any:
    if _RATE_LIMIT > 0:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = [t for t in _rate_hits.get(ip, []) if now - t < 60]
        if len(window) >= _RATE_LIMIT:
            _rate_hits[ip] = window
            return JSONResponse({"ok": False, "error": "rate limit exceeded"}, status_code=429)
        window.append(now)
        _rate_hits[ip] = window
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("COUNCIL_CORS", "*").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------- scheduler
SCHEDULER: dict[str, Any] = {"started": None, "runs": 0, "last_consolidate": None, "last_prune": None}
_consolidated_dates: set[str] = set()
_backup_dates: set[str] = set()
_queue = TaskQueue()


async def _scheduler_loop() -> None:
    while True:
        try:
            now = time.localtime()
            today = time.strftime("%Y-%m-%d")
            if now.tm_hour == 3 and now.tm_min < 20 and today not in _consolidated_dates:
                _consolidated_dates.add(today)
                result = await asyncio.to_thread(nightly_consolidate)
                SCHEDULER["last_consolidate"] = result
                SCHEDULER["runs"] += 1
            if now.tm_hour == 4 and now.tm_min < 20 and today not in _backup_dates:
                _backup_dates.add(today)
                backup = await asyncio.to_thread(backup_create)
                SCHEDULER["last_backup"] = backup
                SCHEDULER["runs"] += 1
            journal_files = sorted(JOURNAL_DIR.glob("*.md")) if JOURNAL_DIR.exists() else []
            if len(journal_files) > 300:
                for old in journal_files[:-300]:
                    try:
                        old.unlink()
                    except OSError:
                        pass
                SCHEDULER["last_prune"] = f"pruned to newest 300 ({time.strftime('%Y-%m-%d %H:%M')})"
                SCHEDULER["runs"] += 1
        except Exception as exc:  # pragma: no cover - scheduler must never die
            print(f"[council] scheduler error: {exc}", flush=True)
        await asyncio.sleep(45)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from council.storage.optimizer import setup_persist_structure

    setup_persist_structure()
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

    async def _task_ask(payload: dict[str, Any]) -> dict[str, Any]:
        req = AskRequest(
            prompt=payload["prompt"],
            strategy=payload.get("strategy", "majority"),
            min_agreement=int(payload.get("min_agreement", 2)),
            mode=payload.get("mode", "together"),
            agent=payload.get("agent"),
        )
        return await ask_council(req)

    async def _task_decompose(payload: dict[str, Any]) -> dict[str, Any]:
        return await run_decomposed(
            payload["prompt"],
            strategy=payload.get("strategy", "majority"),
            min_agreement=int(payload.get("min_agreement", 2)),
        )

    async def _task_debate(payload: dict[str, Any]) -> dict[str, Any]:
        return await run_debate(
            payload["prompt"],
            rounds=int(payload.get("rounds", 3)),
            strategy=payload.get("strategy", "majority"),
            min_agreement=int(payload.get("min_agreement", 2)),
        )

    async def _task_install_agent(payload: dict[str, Any]) -> dict[str, Any]:
        from council.agents.installer import install as agent_install

        return await asyncio.to_thread(agent_install, payload.get("name", ""))

    _queue.register_handler("ask", _task_ask)
    _queue.register_handler("decompose", _task_decompose)
    _queue.register_handler("debate", _task_debate)
    _queue.register_handler("install_agent", _task_install_agent)
    _queue.start()

    SCHEDULER["started"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    task = asyncio.create_task(_scheduler_loop())
    print(f"[council] started (v{__version__}, home={COUNCIL_HOME})", flush=True)
    try:
        yield
    finally:
        task.cancel()
        await _queue.stop()
        try:
            await task
        except asyncio.CancelledError:
            pass


app.router.lifespan_context = lifespan

# ------------------------------------------------------------------- models
class AskRequest(BaseModel):
    prompt: str
    strategy: str = "majority"
    min_agreement: int = 2
    mode: str = "together"
    agent: str | None = None


class DebateRequest(BaseModel):
    prompt: str
    rounds: int = 3
    strategy: str = "majority"
    min_agreement: int = 2


class OptimizeRequest(BaseModel):
    dry_run: bool = False


class CanvasWriteRequest(BaseModel):
    path: str
    content: str = ""


class CanvasMkdirRequest(BaseModel):
    path: str


class VisionAnalyzeRequest(BaseModel):
    path: str | None = None
    prompt: str = "Describe this screenshot in detail."


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    provider: str = "edge"


class RestoreRequest(BaseModel):
    name: str


class TaskRequest(BaseModel):
    kind: str = "ask"  # ask | decompose | debate | install_agent
    prompt: str = ""
    strategy: str = "majority"
    min_agreement: int = 2
    mode: str = "together"
    agent: str | None = None
    rounds: int = 3
    priority: int = 5
    name: str | None = None  # agent name for kind=install_agent


class SecretRequest(BaseModel):
    key: str
    value: str


# ------------------------------------------------------------------ helpers
def _safe_slug(prompt: str, maxlen: int = 40) -> str:
    """Turn free text into a filesystem-safe slug."""
    s = re.sub(r"[^\w\-. ]", "_", prompt, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip())
    s = s.strip("._-")
    if len(s) > maxlen:
        s = s[:maxlen]
    if not s:
        s = "prompt"
    digest = hashlib.sha256(prompt.encode("utf-8", errors="ignore")).hexdigest()[:6]
    return f"{s}-{digest}"


def _append_journal(prompt: str, result: dict[str, Any]) -> Path | None:
    ts = time.strftime("%Y-%m-%d-%H%M%S")
    path = JOURNAL_DIR / f"{ts}-{_safe_slug(prompt)}.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Council Journal {ts}\n\n## Prompt\n{prompt}\n\n## Mode\n{result.get('mode', 'council')}\n\n"
            f"## Strategy\n{result.get('strategy')}\n\n## Votes\n{result.get('votes')}\n\n"
            f"## Final\n{result.get('final')}\n",
            encoding="utf-8",
        )
        return path
    except OSError as exc:
        # journaling is best-effort - never crash a council answer for it
        print(
            f"note: could not write the journal ({exc}). "
            "Set COUNCIL_HOME to a writable folder to keep a journal.",
            file=sys.stderr,
        )
        return None


def _effective_prompt(prompt: str) -> str:
    """Inject relevant prior context (RAG-lite) when memory injection is on."""
    try:
        cfg = config_load()
        inject = bool(cfg.get("council", {}).get("memory_injection", True))
    except Exception:
        inject = True
    if inject and len(prompt.strip()) >= 20:
        try:
            context = retrieve_context(prompt, top_k=3)
        except Exception:
            context = ""
        if context:
            return f"{prompt}\n\n[Relevant prior context]\n{context}"
    return prompt


def _cache_key(req: AskRequest) -> str:
    raw = f"{req.prompt}|{req.strategy}|{req.mode}|{req.agent or ''}|{req.min_agreement}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:32]


def _cache_enabled() -> dict:
    try:
        return dict(config_load().get("council", {}).get("cache", {}))
    except Exception:
        return {"enabled": True, "ttl_seconds": 3600, "max_entries": 500}


async def _probe_agents(timeout: float = 2.0) -> dict[str, Any]:
    from council.orchestrator.agents import client_modes

    agents = build_default_clients()
    modes = client_modes(timeout=1.0)
    results: dict[str, Any] = {}

    async def _one(name: str, client: Any) -> None:
        try:
            r = await client.ask("ping", timeout=timeout)
            results[name] = {
                "status": r.status,
                "latency": round(r.latency, 2),
                "role": r.role,
                "mode": modes.get(name, {}).get("mode", "unknown"),
                "detail": modes.get(name, {}).get("detail", ""),
            }
        except Exception as exc:  # pragma: no cover
            results[name] = {
                "status": f"error: {exc}",
                "role": "",
                "mode": modes.get(name, {}).get("mode", "unknown"),
                "detail": modes.get(name, {}).get("detail", ""),
            }

    await asyncio.gather(*[_one(n, c) for n, c in agents.items()])
    return results


async def _finalize_council(
    req: AskRequest,
    responses: list[AgentResult],
    request_id: str,
    t0: float,
    include_vote_detail: bool = False,
    journal: bool = True,
) -> dict[str, Any]:
    """Vote on responses, build the result, journal it and audit it."""
    agent_responses = [
        {"agent": r.agent, "role": r.role, "response": r.response, "status": r.status} for r in responses
    ]
    vote_result = await run_council_vote(req.prompt, agent_responses, req.strategy, req.min_agreement)
    votes = {v["agent"]: v["vote"] for v in vote_result.get("votes_detail", [])}
    approve = sum(1 for v in votes.values() if v == "approve")
    consensus = bool(vote_result.get("consensus_reached", approve >= req.min_agreement))
    best = max(responses, key=lambda r: len(r.response))

    final = "\n\n".join(
        f"## {r.agent} ({r.role})\n{r.response}\n_Status: {r.status}, latency: {r.latency:.2f}s_"
        for r in responses
    )
    if consensus:
        final = f"# Council Decision - Consensus {approve}/{len(responses)} ✅\n\n" + final
    else:
        final = f"# Council Decision - No Consensus {approve}/{len(responses)} ❌\n\n" + final

    result: dict[str, Any] = {
        "request_id": request_id,
        "strategy": req.strategy,
        "mode": "council",
        "votes": votes,
        "approve_count": approve,
        "consensus_reached": consensus,
        "best_agent": vote_result.get("best_agent") or best.agent,
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
    if include_vote_detail:
        result["vote_result"] = vote_result
    if journal:
        _append_journal(req.prompt, result)
    audit_record(
        {
            "id": request_id,
            "mode": req.mode,
            "strategy": req.strategy,
            "prompt": req.prompt[:200],
            "consensus": consensus,
            "approve": approve,
            "total_agents": len(responses),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "agents": [
                {"agent": r.agent, "status": r.status, "latency": round(r.latency, 2)} for r in responses
            ],
        }
    )
    return result


async def ask_council(
    req: AskRequest, include_vote_detail: bool = False, request_id: str | None = None
) -> dict[str, Any]:
    """Ask all (or one) agent(s), vote, journal, audit. No result caching."""
    rid = request_id or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    prompt_used = _effective_prompt(req.prompt)
    agents = build_default_clients()
    if req.mode == "alone" and req.agent and req.agent in agents:
        responses = [await agents[req.agent].ask(prompt_used)]
    else:
        responses = await asyncio.gather(*[agents[k].ask(prompt_used) for k in agents])
    return await _finalize_council(req, responses, rid, t0, include_vote_detail=include_vote_detail)


def _ws_authorized(ws: WebSocket) -> bool:
    return not _API_KEY or ws.query_params.get("token") == _API_KEY


# ------------------------------------------------------------------- routes
@app.get("/")
def index() -> HTMLResponse:
    try:
        html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
    except Exception:
        html = "<html><body><h1>CouncilKey-Os</h1></body></html>"
    return HTMLResponse(html)


@app.get("/3d")
def index_3d() -> HTMLResponse:
    """Standalone 3D knowledge-graph dashboard (see council/dashboard/three_d.py)."""
    from council.dashboard.three_d import HTML_3D

    return HTMLResponse(HTML_3D)


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"ok": True, "version": __version__})


@app.get("/api/version")
def version() -> JSONResponse:
    return JSONResponse({"version": __version__, "name": "CouncilKey-Os"})


@app.get("/api/system")
def system() -> JSONResponse:
    return JSONResponse(system_info())


@app.get("/api/status")
async def status() -> JSONResponse:
    agents = await _probe_agents(timeout=1.5)
    journal = (
        [{"file": p.name, "size": p.stat().st_size} for p in sorted(JOURNAL_DIR.glob("*.md"))[-20:]]
        if JOURNAL_DIR.exists()
        else []
    )
    ollama = ollama_running()
    from council.llm.provider import provider_status

    provider = provider_status()
    return JSONResponse(
        {
            "version": __version__,
            "agents": agents,
            "council": {"mode": "debate", "consensus": {"strategy": "majority"}},
            "ollama": {
                "running": bool(ollama.get("running")),
                "models": ollama.get("models", []) if ollama.get("running") else [],
            },
            "provider": provider,
            "queue": _queue.stats(),
            "cache": dict(_cache_stats),
            "journal": journal,
        }
    )


@app.get("/api/agents/status")
async def agents_status() -> JSONResponse:
    return JSONResponse(await _probe_agents())


@app.get("/api/setup/status")
def setup_status_route() -> JSONResponse:
    """Status of the setup: provider configured, keys stored, agents installed."""
    from council.agents.setup_wizard import summary as wizard_summary
    from council.llm.provider import provider_status

    provider = provider_status()
    setup = wizard_summary()
    installed_agents = {}
    try:
        from council.agents.installer import status as agent_status

        for name, info in agent_status().items():
            installed_agents[name] = {
                "installed": info["installed"],
                "install": info["install"],
                "binary": info["binary"],
            }
    except Exception:
        pass
    return JSONResponse(
        {
            "provider": provider,
            "setup_summary": setup,
            "agents": installed_agents,
            "setup_done": bool(setup.get("provider")) or any(
                a.get("installed") for a in installed_agents.values()
            ),
        }
    )


@app.get("/api/agents/prereqs")
def agents_prereqs_route() -> JSONResponse:
    from council.agents.installer import check_prereqs

    return JSONResponse(check_prereqs())


@app.post("/api/council/ask")
async def ask(req: AskRequest) -> JSONResponse:
    cache_cfg = _cache_enabled()
    key = _cache_key(req)
    if cache_cfg.get("enabled", True):
        hit = cache_get(key, ttl=float(cache_cfg.get("ttl_seconds", 3600)))
        if hit is not None:
            _cache_stats["hits"] += 1
            hit["cached"] = True
            return JSONResponse(hit)
        _cache_stats["misses"] += 1
    result = await ask_council(req)
    if cache_cfg.get("enabled", True):
        cache_put(key, result, max_entries=int(cache_cfg.get("max_entries", 500)))
    return JSONResponse(result)


@app.post("/api/council/vote")
async def council_vote(req: AskRequest) -> JSONResponse:
    return JSONResponse(await ask_council(req, include_vote_detail=True))


@app.post("/api/council/decompose")
async def council_decompose(req: AskRequest) -> JSONResponse:
    """Decompose a complex prompt into focused subtasks and execute them."""
    t0 = time.perf_counter()
    rid = uuid.uuid4().hex[:12]
    result = await run_decomposed(req.prompt, req.strategy, req.min_agreement)
    _append_journal(req.prompt, result)
    audit_record(
        {
            "id": rid,
            "mode": "decomposed",
            "strategy": req.strategy,
            "prompt": req.prompt[:200],
            "consensus": result["consensus_reached"],
            "approve": result["approve_count"],
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "agents": [{"agent": s["agent"], "status": s["status"], "latency": s["latency"]} for s in result["subtasks"]],
        }
    )
    result["request_id"] = rid
    return JSONResponse(result)


@app.post("/api/council/debate")
async def council_debate(req: DebateRequest) -> JSONResponse:
    """Iterative multi-round debate with revision + convergence detection."""
    t0 = time.perf_counter()
    rid = uuid.uuid4().hex[:12]
    result = await run_debate(req.prompt, rounds=req.rounds, strategy=req.strategy, min_agreement=req.min_agreement)
    _append_journal(req.prompt, result)
    audit_record(
        {
            "id": rid,
            "mode": "debate",
            "strategy": req.strategy,
            "prompt": req.prompt[:200],
            "consensus": result["consensus_reached"],
            "approve": result["approve_count"],
            "rounds": result["rounds"],
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    )
    result["request_id"] = rid
    return JSONResponse(result)


@app.post("/api/council/ask/stream")
async def ask_stream(req: AskRequest) -> StreamingResponse:
    """Stream council progress over Server-Sent Events."""

    async def gen() -> AsyncIterator[str]:
        rid = uuid.uuid4().hex[:12]
        t0 = time.perf_counter()

        def ev(event: str, data: dict[str, Any]) -> str:
            payload = {"event": event, **data}
            return f"data: {json.dumps(payload, default=str)}\n\n"

        yield ev("start", {"prompt": req.prompt, "request_id": rid})
        prompt_used = _effective_prompt(req.prompt)
        agents = build_default_clients()
        tasks = {k: asyncio.create_task(c.ask(prompt_used)) for k, c in agents.items()}
        responses: dict[str, AgentResult] = {}
        for name, task in tasks.items():
            try:
                r = await task
                responses[name] = r
                yield ev(
                    "agent",
                    {
                        "agent": name,
                        "role": r.role,
                        "status": r.status,
                        "latency": round(r.latency, 2),
                        "response": r.response[:1500],
                    },
                )
            except Exception as exc:  # pragma: no cover
                yield ev("error", {"agent": name, "error": str(exc)})
        if len(responses) == len(tasks):
            result = await _finalize_council(req, list(responses.values()), rid, t0)
            yield ev(
                "final",
                {
                    "final": result["final"],
                    "votes": result["votes"],
                    "consensus_reached": result["consensus_reached"],
                    "best_agent": result["best_agent"],
                },
            )
        yield ev("done", {})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.websocket("/ws")
async def ws(ws: WebSocket) -> None:
    await ws.accept()
    if not _ws_authorized(ws):
        await ws.close(code=4401)
        return
    await ws.send_json({"type": "hello", "msg": f"CouncilKey-Os v{__version__} Dashboard WS connected - 3 agents live"})
    try:
        while True:
            data = await ws.receive_json()
            prompt = data.get("prompt", "")
            if not prompt:
                continue
            req = AskRequest(
                prompt=prompt,
                strategy=data.get("strategy", "majority"),
                min_agreement=int(data.get("min_agreement", 2)),
                mode=data.get("mode", "together"),
                agent=data.get("agent"),
            )
            result = await ask_council(req)
            await ws.send_json(result)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/terminal")
async def terminal_ws(ws: WebSocket) -> None:
    if not _ws_authorized(ws):
        await ws.close(code=4401)
        return
    agent = ws.query_params.get("agent", "council")
    await terminal_websocket(ws, agent)


@app.get("/api/journal")
def journal() -> JSONResponse:
    return JSONResponse(list_journal())


@app.get("/api/journal/analyze")
def journal_analyze_route() -> JSONResponse:
    return JSONResponse(journal_analyze())


@app.get("/api/chat/history")
def chat_history(limit: int = 20) -> JSONResponse:
    return JSONResponse({"entries": journal_history(limit=max(1, min(limit, 200)))})


# ------------------------------------------------------------------- tasks
@app.post("/api/tasks")
async def tasks_enqueue(req: TaskRequest) -> JSONResponse:
    payload: dict[str, Any] = {
        "prompt": req.prompt,
        "strategy": req.strategy,
        "min_agreement": req.min_agreement,
        "mode": req.mode,
        "agent": req.agent,
        "rounds": req.rounds,
        "name": req.name,
    }
    task_id = await _queue.enqueue(req.kind, payload, priority=req.priority)
    return JSONResponse({"ok": True, "id": task_id, "kind": req.kind, "status": "queued"})


@app.get("/api/tasks")
async def tasks_list(limit: int = 50) -> JSONResponse:
    return JSONResponse({"tasks": await _queue.list(limit=limit), "stats": _queue.stats()})


@app.get("/api/tasks/{task_id}")
async def tasks_get(task_id: str) -> JSONResponse:
    task = await _queue.get(task_id)
    if task is None:
        return JSONResponse({"ok": False, "error": "task not found"}, status_code=404)
    return JSONResponse(task)


@app.post("/api/tasks/{task_id}/cancel")
async def tasks_cancel(task_id: str) -> JSONResponse:
    cancelled = await _queue.cancel(task_id)
    return JSONResponse({"ok": cancelled})


# ------------------------------------------------------------------- audit
@app.get("/api/audit")
def audit_recent_route(limit: int = 50) -> JSONResponse:
    return JSONResponse({"entries": audit_recent(limit=limit)})


@app.get("/api/audit/stats")
def audit_stats_route() -> JSONResponse:
    return JSONResponse(audit_stats())


# ------------------------------------------------------------------- search
@app.post("/api/search/index")
async def search_index_route() -> JSONResponse:
    result = await asyncio.to_thread(tfidf_build_index)
    return JSONResponse(result)


@app.get("/api/search")
def search_route(q: str = "", top_k: int = 10) -> JSONResponse:
    if not q:
        return JSONResponse({"ok": True, "query": q, "results": [], "total": 0})
    return JSONResponse(tfidf_search(q, top_k=top_k))


# ------------------------------------------------------------------- cache
@app.get("/api/cache/stats")
def cache_stats_route() -> JSONResponse:
    return JSONResponse({**cache_stats(), **{"hits": _cache_stats["hits"], "misses": _cache_stats["misses"]}})


@app.post("/api/cache/flush")
def cache_flush_route() -> JSONResponse:
    cache_flush()
    _cache_stats["hits"] = 0
    _cache_stats["misses"] = 0
    return JSONResponse({"ok": True})


# ------------------------------------------------------------------ secrets
@app.get("/api/secrets")
def secrets_list_route() -> JSONResponse:
    return JSONResponse(vault_list())


@app.get("/api/secrets/status")
def secrets_status_route() -> JSONResponse:
    return JSONResponse(vault_status())


@app.get("/api/secrets/{key}")
def secrets_mask_route(key: str) -> JSONResponse:
    return JSONResponse(vault_mask(key))


@app.post("/api/secrets")
def secrets_set_route(req: SecretRequest) -> JSONResponse:
    return JSONResponse(vault_set(req.key, req.value))


@app.delete("/api/secrets/{key}")
def secrets_delete_route(key: str) -> JSONResponse:
    return JSONResponse(vault_delete(key))


# ----------------------------------------------------------------- storage
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


@app.post("/api/backup/restore")
def backup_restore_route(req: RestoreRequest) -> JSONResponse:
    return JSONResponse(backup_restore(req.name))


@app.get("/api/llm/available")
def llm_available_route() -> JSONResponse:
    from council.llm.manager import available as llm_available

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
    return JSONResponse(skills_evolve())


@app.get("/api/skills/list")
def skills_list_route() -> JSONResponse:
    return JSONResponse(list_skills())


@app.get("/api/skills/read")
def skills_read_route(name: str = "") -> JSONResponse:
    return JSONResponse(read_skill(name))


@app.get("/api/memory/summary")
def memory_summary_route() -> JSONResponse:
    return JSONResponse(memory_summary())


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
    try:
        return JSONResponse(lancedb_search(q, limit=min(limit, 50)))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc), "results": []})


@app.post("/api/embeddings/add")
def embeddings_add(body: dict[str, object]) -> JSONResponse:
    docs = body.get("docs", [])
    if not isinstance(docs, list):
        docs = [str(docs)]
    try:
        return JSONResponse(lancedb_add([str(x) for x in docs]))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.get("/api/ollama/status")
def ollama_status_route() -> JSONResponse:
    return JSONResponse(ollama_running())


@app.post("/api/ollama/chat")
def ollama_chat_route(body: dict[str, object]) -> JSONResponse:
    model = str(body.get("model", "qwen2.5:3b"))
    prompt = str(body.get("prompt", ""))
    system = str(body.get("system", ""))
    return JSONResponse(ollama_chat(model, prompt, system))


@app.get("/api/ollama/models")
def ollama_models_route() -> JSONResponse:
    return JSONResponse(ollama_list_models())


@app.post("/api/ollama/pull")
def ollama_pull_route(body: dict[str, object]) -> JSONResponse:
    model = str(body.get("model", "qwen2.5:3b"))
    return JSONResponse(ollama_pull(model))


@app.post("/api/ollama/delete")
def ollama_delete_route(body: dict[str, object]) -> JSONResponse:
    model = str(body.get("model", ""))
    if not model:
        return JSONResponse({"ok": False, "error": "model required"})
    return JSONResponse(ollama_delete(model))


@app.post("/api/ollama/show")
def ollama_show_route(body: dict[str, object]) -> JSONResponse:
    model = str(body.get("model", ""))
    if not model:
        return JSONResponse({"ok": False, "error": "model required"})
    return JSONResponse(ollama_show(model))


@app.post("/api/ollama/ensure")
def ollama_ensure_route(body: dict[str, object]) -> JSONResponse:
    models = body.get("models")
    if not isinstance(models, list):
        models = ["qwen2.5:3b", "deepseek-coder:1.3b", "nomic-embed-text"]
    return JSONResponse(ollama_ensure_models(models))


@app.get("/api/ollama/defaults")
def ollama_defaults_route() -> JSONResponse:
    return JSONResponse(ollama_get_defaults())


@app.get("/api/knowledge/graph")
def knowledge_graph_route() -> JSONResponse:
    from council.knowledge.graph import _load as graph_load

    return JSONResponse(graph_load())


@app.get("/api/knowledge/search")
def knowledge_search_route(q: str = "") -> JSONResponse:
    from council.knowledge.graph import search as graph_search

    return JSONResponse(graph_search(q))


@app.post("/api/knowledge/node")
def knowledge_add_node(body: dict[str, object]) -> JSONResponse:
    from council.knowledge.graph import add_node

    node_id = str(body.get("id", ""))
    label = str(body.get("label", ""))
    kind = str(body.get("kind", "concept"))
    if not node_id or not label:
        return JSONResponse({"ok": False, "error": "id and label required"})
    return JSONResponse(add_node(node_id, label, kind))


@app.post("/api/knowledge/edge")
def knowledge_add_edge(body: dict[str, object]) -> JSONResponse:
    from council.knowledge.graph import add_edge

    source = str(body.get("source", ""))
    target = str(body.get("target", ""))
    relation = str(body.get("relation", "related"))
    if not source or not target:
        return JSONResponse({"ok": False, "error": "source and target required"})
    return JSONResponse(add_edge(source, target, relation))


@app.get("/api/terminal/status")
def terminal_status_route() -> JSONResponse:
    return JSONResponse({"pty": True, "agent": "council", "guard": True})


@app.get("/api/optional/agents")
def optional_agents_route() -> JSONResponse:
    return JSONResponse({"crewai": False, "microsoft": False, "llm_judge": True})


@app.get("/api/update/check")
def update_check_route() -> JSONResponse:
    return JSONResponse(update_check())


@app.get("/api/metrics")
def metrics_route() -> JSONResponse:
    queue_stats = _queue.stats()
    audit = audit_stats()
    return JSONResponse(
        {
            **metrics_snapshot(request_count=_requests),
            "queue": queue_stats,
            "cache": dict(_cache_stats),
            "audit": {"total": audit.get("total", 0), "consensus_rate": audit.get("consensus_rate")},
        }
    )


@app.get("/api/scheduler/status")
def scheduler_status_route() -> JSONResponse:
    return JSONResponse({**SCHEDULER, "queue": _queue.stats()})


# ------------------------------------------------------------------- vision
@app.get("/api/vision/status")
def vision_status_route() -> JSONResponse:
    from council.vision.screenshot.analyzer import vision_screenshot_tools

    ollama = ollama_running()
    models = ollama.get("models", []) if ollama.get("running") else []
    vision_models = [m for m in models if any(k in str(m).lower() for k in ("vl", "llava", "vision"))]
    return JSONResponse(
        {
            "ollama_running": bool(ollama.get("running")),
            "vision_models": vision_models,
            "tools": vision_screenshot_tools(),
        }
    )


@app.post("/api/vision/screenshot")
def vision_screenshot_route() -> JSONResponse:
    from council.vision.screenshot.analyzer import take_screenshot

    return JSONResponse(take_screenshot())


@app.post("/api/vision/upload")
async def vision_upload_route(file: UploadFile = File(...)) -> JSONResponse:
    from council.vision.screenshot.analyzer import save_upload

    raw = await file.read()
    if not raw:
        return JSONResponse({"ok": False, "error": "empty upload"})
    return JSONResponse(save_upload(raw, file.filename or "upload.png"))


@app.post("/api/vision/analyze")
def vision_analyze_route(req: VisionAnalyzeRequest) -> JSONResponse:
    from council.vision.screenshot.analyzer import analyze_screenshot

    return JSONResponse(analyze_screenshot(req.path, req.prompt))


# -------------------------------------------------------------------- voice
@app.get("/api/voice/status")
def voice_status_route() -> JSONResponse:
    from council.voice.chat.chat import voice_status

    return JSONResponse(voice_status())


@app.post("/api/voice/tts")
async def voice_tts_route(req: TTSRequest) -> JSONResponse:
    from council.voice.chat.chat import tts

    result = await asyncio.to_thread(tts, req.text, req.voice, req.provider)
    if result.get("ok"):
        result["url"] = "/api/voice/audio/" + result["name"]
    return JSONResponse(result)


@app.get("/api/voice/audio/{name}")
def voice_audio_route(name: str):
    if "/" in name or "\\" in name or not name.endswith((".mp3", ".wav", ".ogg")):
        return JSONResponse({"ok": False, "error": "invalid audio name"}, status_code=400)
    from council.voice.chat.chat import AUDIO_DIR

    path = AUDIO_DIR / name
    if not path.exists():
        return JSONResponse({"ok": False, "error": "audio not found"}, status_code=404)
    return FileResponse(path, media_type="audio/mpeg")


@app.post("/api/voice/transcribe")
async def voice_transcribe_route(file: UploadFile = File(...)) -> JSONResponse:
    from council.voice.chat.chat import AUDIO_DIR, transcribe

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe = "".join(c for c in (file.filename or "audio") if c.isalnum() or c in "._-")[:60]
    path = AUDIO_DIR / f"rec-{ts}-{safe}"
    path.write_bytes(await file.read())
    result = await asyncio.to_thread(transcribe, str(path))
    if result.get("ok"):
        result["path"] = str(path)
    return JSONResponse(result)


# ------------------------------------------------------------------- canvas
@app.get("/api/canvas/files")
def canvas_files_route(path: str = "") -> JSONResponse:
    from council.canvas.desktop import list_dir

    return JSONResponse(list_dir(path))


@app.get("/api/canvas/read")
def canvas_read_route(path: str = "") -> JSONResponse:
    from council.canvas.desktop import read_file

    return JSONResponse(read_file(path))


@app.post("/api/canvas/write")
def canvas_write_route(req: CanvasWriteRequest) -> JSONResponse:
    from council.canvas.desktop import write_file

    return JSONResponse(write_file(req.path, req.content))


@app.post("/api/canvas/mkdir")
def canvas_mkdir_route(req: CanvasMkdirRequest) -> JSONResponse:
    from council.canvas.desktop import make_dir

    return JSONResponse(make_dir(req.path))


# ------------------------------------------------------------------ browser
@app.get("/api/browser/fetch")
def browser_fetch_route(url: str = "") -> JSONResponse:
    from council.browser.camofox.browser import fetch

    return JSONResponse(fetch(url))


# --------------------------------------------------------------------- main
def cli_dashboard(port: int = 8000, host: str = "0.0.0.0") -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli_dashboard()
