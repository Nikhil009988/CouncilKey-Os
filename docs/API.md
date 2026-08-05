# CouncilKey-Os API Reference

Base URL: `https://council.local:8443` or `http://localhost:8443` or `http://localhost:8000`

Auto-generated OpenAPI docs: `/docs` (Swagger) and `/redoc` (ReDoc) when running FastAPI.

## Council APIs

### POST /api/council/ask

Broadcast prompt to 3 agents in parallel, vote, return final synthesis.

**Request:**
```json
{
  "prompt": "Build me a minimal website - debate!",
  "strategy": "majority" // majority, weighted, llm_judge, hermes_decides
}
```

**Response:**
```json
{
  "strategy": "majority",
  "votes": {"hermes": "approve", "openclaw": "approve", "agent-zero": "approve"},
  "approve_count": 3,
  "consensus_reached": true,
  "best_agent": "agent-zero",
  "final": "# Council Decision - Consensus 3/3 ✅\n...",
  "responses": [
    {"agent": "hermes", "role": "memory", "response": "...", "latency": 0.5, "status": "mock|live"},
    {"agent": "openclaw", "role": "action", "response": "...", "latency": 0.6, "status": "mock|live"},
    {"agent": "agent-zero", "role": "builder", "response": "...", "latency": 0.7, "status": "mock|live"}
  ],
  "timestamp": "2026-08-04T00:00:00"
}
```

**Real adapters:**
- OpenClaw: Tries POST http://127.0.0.1:18789/api/message with Bearer token from podman secret / file / env / ~/.openclaw/gateway.token, multiple endpoints fallback, circuit breaker 3 fails open 60s
- Hermes: POST http://127.0.0.1:18790/api/message
- Agent Zero: POST http://127.0.0.1:50001/api/message {text, context}
- Fallback mock if offline (graceful degradation for offline pendrive like Reefy LAN offline)

**Voting strategies:**
- `majority`: Need min_agreement (default 2) approvals, each agent votes approve unless response contains "danger"
- `weighted`: Sum weights from council.yaml
- `llm_judge`: Uses LiteLLM (Agent Zero litellm==1.88.1) to judge best response, needs API key from secrets, fallback longest if no key
- `hermes_decides`: Sage has final say

### GET /api/status

Agent status + council config + journal.

**Response:**
```json
{
  "agents": {
    "hermes": {"status": "online|offline (mock)", "role": "memory", "port": 18790},
    "openclaw": {"status": "online", "role": "action", "port": 18789},
    "agent0": {"status": "offline (mock)", "role": "builder", "port": 50001}
  },
  "council": {"mode": "debate", "consensus": {"strategy": "majority"}},
  "journal": [{"file": "2026-08-04-abc123.md", "size": 6365}]
}
```

Health check: `curl -f http://localhost:8443/api/status`

## Storage Optimizer APIs

### GET /api/storage/audit

From `council/storage/optimizer.py` audit() - keep vs cache per agent.

**Response:**
```json
{
  "timestamp": "2026-08-04T00:00:00",
  "council_home": "/var/lib/council",
  "agents": {
    "hermes": {"keep_size": 160, "keep_size_human": "160.0B", "keep_files": 8, "cache_persist_size": 0, "cache_ram_size": 5242880, "cache_ram_human": "5.0MB"},
    "openclaw": {...},
    "agent-zero": {...},
    "journal": {"keep_size": 6365, "keep_size_human": "6.2KB"}
  },
  "total_keep": 6595,
  "total_keep_human": "6.4KB",
  "total_cache_ram": 5242898,
  "total_cache_ram_human": "5.0MB",
  "total_cache_persist_leaked": 0,
  "total_cache_persist_leaked_human": "0.0B"
}
```

Keep: 100-300MB after 1 year smart (SOUL MEMORY USER skills knowledge custom solutions) vs Cache RAM: 1-10GB heavy auto delete on unplug.

### GET /api/storage/what-if

What would be deleted on unplug.

**Response:**
```json
{
  "timestamp": "...",
  "files": [
    {"path": "/tmp/council/hermes/logs/agent.log", "size": 5242880, "human": "5.0MB", "reason": "tmpfs RAM - auto delete on unplug", "agent": "hermes", "type": "cache_ram"},
    {"path": "/var/lib/council/hermes/real_home/sessions/...", "size": 1000000, "human": "1.0MB", "reason": "heavy sessions - safe to delete, distilled kept", "agent": "hermes", "type": "cache_persist_leaked"}
  ],
  "total_files": 2,
  "total_size": 5242898,
  "total_size_human": "5.0MB",
  "message": "RAW heavy data (sessions, logs, caches) -> DELETE. Distilled -> KEEP and makes you smarter daily."
}
```

### POST /api/storage/optimize

Optimize: archives unused skills >90d not pinned, cleans workdir >7d not in solutions, compresses journal >30d to .gz.

**Request:** `{"dry_run": false}`

**Response:**
```json
{
  "timestamp": "...",
  "actions": ["Archived unused skill my-old-skill", "Deleted old workdir old_build.py 1.2MB", "Compressed journal 2026-07-01-abc.md 10KB->2KB"],
  "saved_bytes": 1234567,
  "saved_human": "1.2MB",
  "dry_run": false
}
```

### POST /api/storage/setup

Setup optimized keep/cache split with tmpfs symlinks (first boot).

**Response:** `{"ok": true, "home": "/var/lib/council"}`

## Journal APIs

### GET /api/journal

Git versioned council decisions.

**Response:**
```json
{
  "journal_dir": "/var/lib/council/journal",
  "files": [
    {"file": "2026-08-04-abc123.md", "size": 6365, "content": "# Council Journal ..."}
  ]
}
```

## WebSocket

### WS /ws

Real-time council chat.

**Client sends:**
```json
{"prompt": "Build website"}
```

**Server sends:**
```json
{
  "strategy": "majority",
  "votes": {...},
  "final": "...",
  "responses": [...]
}
```

Also: `{"type":"hello","msg":"CouncilKey-Os v2 Dashboard WS connected - 3 agents live"}` on connect.

## CLI Equivalent

```bash
council status
council ask "hello council"
council ask --strategy llm_judge "prompt"
council storage-audit
council storage-what-if
council storage-optimize
council storage-setup
council journal
council dashboard --port 8443 --host 0.0.0.0
```

## Auth

- v1: No auth, LAN only (like Reefy)
- Production: Add BasicAuth via `auth_login`/`auth_password` from Agent Zero settings pattern, or Tailscale auth key from env `TAILSCALE_AUTHKEY`
- Secrets edit via GPG requires master password (LUKS passphrase)
- OpenAPI docs at `/docs` protected by auth in production (use `auth_login` from settings)

## Metrics

### GET /api/metrics

Returns CPU/RAM/storage per agent via `podman stats` + `df`.

```json
{
  "agents": {
    "hermes": {"cpu": "5%", "ram": "200MB", "storage_keep": "45MB", "status": "online"},
    "openclaw": {"cpu": "2%", "ram": "100MB", "storage_keep": "30MB"},
    "agent-zero": {"cpu": "10%", "ram": "500MB", "storage_keep": "20MB"}
  },
  "host": {"cpu": "20%", "ram": "4GB/8GB", "storage_total": "120GB", "storage_keep_total": "230MB", "storage_cache_ram": "1.2GB"}
}
```

## OpenAPI

When running `python3 council/orchestrator/main.py dashboard`, visit:

- Swagger UI: `http://localhost:8443/docs`
- ReDoc: `http://localhost:8443/redoc`
- OpenAPI JSON: `http://localhost:8443/openapi.json`

---

# v1.1.0 - New Endpoints & Features

## System
| Method | Path | Description |
|---|---|---|
| GET | `/api/version` | Package version |
| GET | `/api/system` | Host info: platform, python, cpu count, uptime, disk, council home |
| GET | `/api/agents/status` | Live probe of hermes/openclaw/agent-zero gateways (2s timeout, mock fallback) |
| GET | `/api/scheduler/status` | Background scheduler state (nightly consolidation, journal prune) |
| GET | `/api/metrics` | Now includes `uptime_seconds`, `disk`, `request_count`, `storage_split` |

## Council & Knowledge
| Method | Path | Description |
|---|---|---|
| POST | `/api/council/vote` | Same as `/api/council/ask` but includes full `vote_result` (strategy detail) |
| GET | `/api/chat/history?limit=20` | Journal parsed into prompt/final chat-history entries |
| GET | `/api/knowledge/search?q=` | Substring search over knowledge-graph nodes |
| GET | `/api/skills/list` | List evolved skills |
| GET | `/api/skills/read?name=` | Read a single skill |
| GET | `/api/memory/summary` | Hermes long-term memory preview (chars/lines/preview) |

## Backups & Ollama
| Method | Path | Description |
|---|---|---|
| POST | `/api/backup/restore` | `{"name": "council-2026-08-05.tar.gz"}` - restores keep dirs from a backup (name-validated) |
| POST | `/api/ollama/delete` | `{"model": "qwen2.5:3b"}` - delete a model |
| POST | `/api/ollama/show` | `{"model": "..."}` - model metadata via `/api/show` |

## Vision
| Method | Path | Description |
|---|---|---|
| GET | `/api/vision/status` | Ollama running + installed vision models (llava/qwen2.5vl/...) |
| POST | `/api/vision/screenshot` | Capture desktop to `hermes/cache/screenshots/` (PIL -> gnome-screenshot -> scrot -> imagemagick) |
| POST | `/api/vision/upload` | Multipart `file` upload -> saved screenshot path |
| POST | `/api/vision/analyze` | `{"path": "...", "prompt": "..."}` - analyze with local vision model |

## Voice
| Method | Path | Description |
|---|---|---|
| GET | `/api/voice/status` | Provider availability (edge_tts, elevenlabs, openai_tts, whisper_local) |
| POST | `/api/voice/tts` | `{"text": "...", "voice": "en-US-JennyNeural", "provider": "edge"}` -> `{ok, url}` (mp3 served from `/api/voice/audio/{name}`) |
| GET | `/api/voice/audio/{name}` | Play a generated mp3 |
| POST | `/api/voice/transcribe` | Multipart audio file -> text via local Whisper |

## Canvas (sandboxed file browser inside COUNCIL_HOME)
| Method | Path | Description |
|---|---|---|
| GET | `/api/canvas/files?path=shared` | List directory entries (name/type/size/modified) |
| GET | `/api/canvas/read?path=shared/note.md` | Read text file (200KB cap) |
| POST | `/api/canvas/write` | `{"path": "shared/note.md", "content": "..."}` - write file |
| POST | `/api/canvas/mkdir` | `{"path": "shared/docs"}` - create directory |

Traversal (`../`, absolute paths outside home) is rejected.

## Browser
| Method | Path | Description |
|---|---|---|
| GET | `/api/browser/fetch?url=https://...` | Fetch page -> title + readable text + status (http/https only) |

## Security (new)
- Set `COUNCIL_API_KEY` to require auth: `Authorization: Bearer <key>` or `?token=<key>` on every route except `/` and `/api/health`; WebSockets use `?token=`
- `COUNCIL_RATE_LIMIT=<n>` enables per-IP requests/minute limiting (0 = off)
- `COUNCIL_CORS=*` (default) or comma-separated origins
- Security headers on all responses (nosniff, referrer-policy, permissions-policy)

## CLI (`councilkey`)
```
councilkey serve [--host 0.0.0.0] [--port 8443]
councilkey doctor          # environment health report (exit code 0/1)
councilkey storage [--dry-run]
councilkey version
```

## systemd service
```
sudo ./deploy/install.sh   # installs /opt/councilkey + enables councilkey.service
```

## No-traces audit
```
COUNCIL_HOME=/var/lib/council ./scripts/verify-no-traces.sh         # 7 checks
COUNCIL_HOME=/var/lib/council ./scripts/verify-no-traces.sh --clean # audit + delete
```

---

# v1.2.0 - Advanced Orchestration & Intelligence

## Council modes
| Method | Path | Description |
|---|---|---|
| POST | `/api/council/ask` | Standard ask — now cached (config `council.cache`) and returns `request_id` |
| POST | `/api/council/ask/stream` | Server-Sent Events stream: `start` → `agent` (per response) → `final` → `done` |
| POST | `/api/council/decompose` | `{"prompt": ...}` — splits the prompt into 3 role-based subtasks (Analysis/Hermes, Execution/OpenClaw, Review/AgentZero), executes them, votes on the combined result |
| POST | `/api/council/debate` | `{"prompt": ..., "rounds": 3}` — iterative debate: agents see each other's answers and revise; stops early on convergence (similarity ≥ 0.85 or CONFIRM) |

## Task queue
| Method | Path | Description |
|---|---|---|
| POST | `/api/tasks` | `{"kind": "ask"|"decompose"|"debate", "prompt": ..., "priority": 0-9}` — enqueue for background execution |
| GET | `/api/tasks?limit=` | List tasks + queue stats |
| GET | `/api/tasks/{id}` | Task detail (status/result/error) |
| POST | `/api/tasks/{id}/cancel` | Cancel a queued task |

## Audit trail (JSONL under COUNCIL_HOME/audit/)
| Method | Path | Description |
|---|---|---|
| GET | `/api/audit?limit=` | Recent audit records (request id, mode, strategy, consensus, per-agent latency/status) |
| GET | `/api/audit/stats` | Aggregates: consensus rate, avg duration, per-agent live/mock counts, per-strategy breakdown |

## Full-text search (pure-Python TF-IDF over journal + shared docs)
| Method | Path | Description |
|---|---|---|
| POST | `/api/search/index` | Rebuild the TF-IDF index |
| GET | `/api/search?q=&top_k=` | Ranked search with scores + previews |

## Result cache
| Method | Path | Description |
|---|---|---|
| GET | `/api/cache/stats` | Entries, expired, hits/misses |
| POST | `/api/cache/flush` | Clear the cache |

## Encrypted secrets vault (Fernet if available, HMAC-CTR stdlib fallback)
| Method | Path | Description |
|---|---|---|
| GET | `/api/secrets` | Key names + backend (never values) |
| GET | `/api/secrets/{key}` | Masked hint (`sk******90`) |
| POST | `/api/secrets` | `{"key": ..., "value": ...}` — store encrypted (key from `COUNCIL_MASTER_KEY` or `.master_key` file) |
| DELETE | `/api/secrets/{key}` | Remove a secret |

## Other v1.2 changes
- **Memory injection (RAG-lite)**: prompts ≥ 20 chars get relevant journal/knowledge/vector-store context injected before agents see them (config `council.memory_injection`)
- **Terminal command guard**: dangerous commands (`rm -rf /`, `mkfs`, `dd`, fork bomb, shutdown...) are blocked before reaching the PTY; `!force` prefix or `shared/terminal-allowlist.txt` overrides
- **Scheduler**: adds automatic daily backup at 04:00 alongside nightly consolidation; `/api/scheduler/status` shows queue stats
- **`/api/status` and `/api/metrics`** now include queue depth, cache hits/misses and audit totals
- **Dashboard**: new Tasks tab (enqueue/monitor background tasks), Intelligence tab (TF-IDF search, cache stats, audit analytics), and a Stream toggle for the council chat

---

# v1.3.0 - Agent Installer

The three agents (Hermes, OpenClaw, Agent Zero) are downloaded automatically by
`./scripts/setup.sh` (or the `install.sh` one-liner) from their official GitHub
repos into `tools/linux/` (override with `COUNCIL_AGENTS_DIR`).

## CLI
```
councilkey agents              # status table (installed? running? port?)
councilkey agents install      # download + configure all 3 agents
councilkey agents install hermes openclaw
councilkey agents start        # best-effort launch of installed agents
councilkey agents start agent-zero
```

## API
| Method | Path | Description |
|---|---|---|
| GET | `/api/agents/prereqs` | Tool availability: git, python3, node, npm, uv |
| POST | `/api/tasks` | `{"kind": "install_agent", "name": "hermes", "priority": 5}` — download an agent as a background task; monitor via `/api/tasks/{id}` |

Installed agents show up in `GET /api/status` and `/api/agents/status` as
`running` (their gateway port answers), `installed`, or `not installed`.

> Note: installing an agent clones its official repository (Hermes ~200MB,
> Agent Zero's Python deps can be several GB including torch). Needs internet
> + git on first run. Each agent's own README documents the canonical start
> command; `councilkey agents start` tries common launchers and falls back to
> printing the right hint.

---

# v1.4.0 - Local LLM agents (agents that actually work)

## The 3 agents now have a real, working brain by default

Each council role is answered by a local Ollama model with a distinct system
prompt (no API keys, offline):

| Role | Agent | Default model |
|---|---|---|
| memory & analysis | hermes | qwen2.5:3b |
| action & execution | openclaw | qwen2.5:3b |
| builder & review | agent-zero | deepseek-coder:1.3b (falls back to qwen2.5:3b) |

Fallback chain per agent (in `/api/status` as `mode`):
1. **gateway** - an external agent server answers on its URL
   (`COUNCIL_HERMES_URL` / `COUNCIL_OPENCLAW_URL` / `COUNCIL_AGENTZERO_URL`)
2. **local-llm** - Ollama is running (any model; preferred model picked first)
3. **mock** - nothing available; explicitly labeled, never silent

## CLI
```
councilkey llm status         # ollama running? models? recommended pull
councilkey llm install        # install Ollama (winget on Windows)
councilkey llm pull [model]   # download a model (default qwen2.5:3b, ~1.9GB)
councilkey agents verify      # real smoke test: asks each agent, shows backend
```

## Windows
- `scripts/setup.ps1` - full setup (venv, agents, Ollama via winget, model pull, tests)
- `scripts/start.ps1` / `scripts/start.bat` - start the dashboard (auto-starts Ollama)

## Real vs dev-only
For real use, the 3 agents run on genuine Ollama:
`councilkey llm install && councilkey llm pull` (or run `scripts/setup.sh`,
which does it automatically).

A dev-only, clearly-labeled Ollama-compatible fixture lives at
`scripts/dev/llm-demo-server.py` for CI/sandbox testing. It is NOT part of
the product and is never used by setup, start, or the dashboard.
