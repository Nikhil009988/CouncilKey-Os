# CouncilKey-Os API - Production Grade

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

**Production real adapters:**
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

## Storage Optimizer APIs (Production)

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

## Auth (Production)

- v1: No auth, LAN only (like Reefy)
- Production: Add BasicAuth via `auth_login`/`auth_password` from Agent Zero settings pattern, or Tailscale auth key from env `TAILSCALE_AUTHKEY`
- Secrets edit via GPG requires master password (LUKS passphrase)
- OpenAPI docs at `/docs` protected by auth in production (use `auth_login` from settings)

## Metrics (Production)

### GET /api/metrics (to be implemented)

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
