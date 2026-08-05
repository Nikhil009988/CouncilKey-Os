"""CouncilKey-Os Council Core - FastAPI + WebSocket orchestrator (v1.1.0).

Fixes over v1.0:
- WebSocket chat no longer crashes serializing JSONResponse bytes
- Journal filenames are sanitized (no nested paths from "/" prompts)
- Optional API-key auth, security headers, CORS, request logging, rate limiting
- Startup persistence layout + background scheduler (nightly consolidation)
- Live agent status probing, /api/version, /api/system, chat history,
  backup restore, knowledge search, skills list, memory summary,
  vision/voice/canvas/browser endpoints (see docs/API.md)
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from council import __version__
from council.backup.manager import create_backup as backup_create
from council.backup.manager import list_backups as backup_list
from council.backup.manager import restore_backup as backup_restore
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
from council.metrics.snapshot import snapshot as metrics_snapshot
from council.network.tailscale import setup_tailscale, tailscale_status
from council.orchestrator.agents import build_default_clients
from council.orchestrator.voting import run_council_vote
from council.reflection.self import reflect_on_last
from council.skills.evolution import evolve as skills_evolve
from council.skills.evolution import list_skills, read_skill
from council.system.info import collect as system_info
from council.terminal.websocket import terminal_websocket
from council.update.manager import check_update as update_check

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
JOURNAL_DIR = COUNCIL_HOME / "journal"

AGENT_PORTS = {"hermes": 18790, "openclaw": 18789, "agent-zero": 50001}

app = FastAPI(title="CouncilKey-Os", version=__version__)

# ---------------------------------------------------------------- middleware
_requests = 0
_rate_hits: dict[str, list[float]] = {}
_RATE_LIMIT = int(os.environ.get("COUNCIL_RATE_LIMIT", "0"))  # requests/min/IP, 0 = off
_API_KEY = os.environ.get("COUNCIL_API_KEY", "")


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
    SCHEDULER["started"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    task = asyncio.create_task(_scheduler_loop())
    print(f"[council] started (v{__version__}, home={COUNCIL_HOME})", flush=True)
    try:
        yield
    finally:
        task.cancel()
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


def _append_journal(prompt: str, result: dict[str, Any]) -> Path:
    ts = time.strftime("%Y-%m-%d-%H%M%S")
    path = JOURNAL_DIR / f"{ts}-{_safe_slug(prompt)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Council Journal {ts}\n\n## Prompt\n{prompt}\n\n## Strategy\n{result.get('strategy')}\n\n"
        f"## Votes\n{result.get('votes')}\n\n## Final\n{result.get('final')}\n",
        encoding="utf-8",
    )
    return path


async def _probe_agents(timeout: float = 2.0) -> dict[str, Any]:
    agents = build_default_clients()
    results: dict[str, Any] = {}

    async def _one(name: str, client: Any) -> None:
        try:
            r = await client.ask("ping", timeout=timeout)
            results[name] = {"status": r.status, "latency": round(r.latency, 2), "role": r.role, "port": AGENT_PORTS.get(name)}
        except Exception as exc:  # pragma: no cover
            results[name] = {"status": f"error: {exc}", "role": "", "port": AGENT_PORTS.get(name)}

    await asyncio.gather(*[_one(n, c) for n, c in agents.items()])
    return results


async def ask_council(req: AskRequest, include_vote_detail: bool = False) -> dict[str, Any]:
    agents = build_default_clients()
    if req.mode == "alone" and req.agent and req.agent in agents:
        responses = [await agents[req.agent].ask(req.prompt)]
    else:
        responses = await asyncio.gather(*[agents[k].ask(req.prompt) for k in agents])

    agent_responses = [
        {"agent": r.agent, "role": r.role, "response": r.response, "status": r.status}
        for r in responses
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
        "strategy": req.strategy,
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
    _append_journal(req.prompt, result)
    return result


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
    return JSONResponse(
        {
            "version": __version__,
            "agents": agents,
            "council": {"mode": "debate", "consensus": {"strategy": "majority"}},
            "ollama": {"running": bool(ollama.get("running"))},
            "journal": journal,
        }
    )


@app.get("/api/agents/status")
async def agents_status() -> JSONResponse:
    return JSONResponse(await _probe_agents())


@app.post("/api/council/ask")
async def ask(req: AskRequest) -> JSONResponse:
    return JSONResponse(await ask_council(req))


@app.post("/api/council/vote")
async def council_vote(req: AskRequest) -> JSONResponse:
    return JSONResponse(await ask_council(req, include_vote_detail=True))


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
    return JSONResponse({"pty": True, "agent": "council"})


@app.get("/api/optional/agents")
def optional_agents_route() -> JSONResponse:
    return JSONResponse({"crewai": False, "microsoft": False, "llm_judge": True})


@app.get("/api/update/check")
def update_check_route() -> JSONResponse:
    return JSONResponse(update_check())


@app.get("/api/metrics")
def metrics_route() -> JSONResponse:
    return JSONResponse(metrics_snapshot(request_count=_requests))


@app.get("/api/scheduler/status")
def scheduler_status_route() -> JSONResponse:
    return JSONResponse(SCHEDULER)


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
