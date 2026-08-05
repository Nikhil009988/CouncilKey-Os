# Changelog

## v1.1.0 (2026-08-05)

### Added
- **Working vision pipeline**: `/api/vision/status`, `/api/vision/screenshot`, `/api/vision/upload`, `/api/vision/analyze` (local Ollama vision models like llava/qwen2.5vl)
- **Working voice pipeline**: `/api/voice/status`, `/api/voice/tts` (Edge TTS free default, ElevenLabs, OpenAI), `/api/voice/audio/{name}`, `/api/voice/transcribe` (local Whisper)
- **Canvas file browser**: `/api/canvas/files|read|write|mkdir` with strict path confinement inside `COUNCIL_HOME`
- **Browser toolkit**: `/api/browser/fetch` with HTML→text extraction (stdlib only)
- **`councilkey` CLI**: `serve`, `doctor`, `storage`, `version` console script
- **Security**: optional `COUNCIL_API_KEY` auth (header or `?token=`), security headers, CORS via `COUNCIL_CORS`, rate limiting via `COUNCIL_RATE_LIMIT`, request logging
- **Background scheduler**: nightly memory consolidation (3 AM) + journal pruning (>300 entries)
- **More endpoints**: `/api/system`, `/api/version`, `/api/agents/status`, `/api/chat/history`, `/api/backup/restore`, `/api/knowledge/search`, `/api/skills/list`, `/api/skills/read`, `/api/memory/summary`, `/api/ollama/delete`, `/api/ollama/show`, `/api/scheduler/status`, `/api/vision/*`, `/api/voice/*`, `/api/canvas/*`, `/api/browser/fetch`
- **Tooling**: real `scripts/verify-no-traces.sh` (7 checks, `--clean`), real `scripts/tailscale-setup.sh`, `deploy/councilkey.service` + `deploy/install.sh`
- **Working bootc containers**: dev/qcow2 variant runs the orchestrator with healthcheck; prod variant runs it as a hardened systemd service
- **Knowledge graph**: dedupe on add + substring search
- **Voting**: richer danger signals, confidence scoring, cached strategy instances
- **Tests**: 21 tests covering v1.1 features (voting, graph, backups, API, WS, canvas confinement, CLI, shell syntax, no-traces audit)

### Fixed
- WebSocket `/ws` crashed serializing `JSONResponse.body` bytes -> now sends plain dicts
- Journal filenames could create nested paths when prompts contained `/` -> sanitized slugs with hash suffix
- Update checker pointed at stale fork `nikhilgundu99/CouncilKey-Os` -> `Nikhil009988/CouncilKey-Os` (+ env override)
- `/api` sub-app mount in `council/dashboard/app.py` produced broken `/api/api/...` routes -> clean alias
- Dead `council/storage/optimizer_import.py` removed
- 109 ruff lint issues cleaned (import order, duplicate imports, unused vars)
- Agent gateway token files are now read with proper context managers
- `/api/status` reported agents "online" unconditionally -> live probing with timeout
- README badges/branch names updated to match reality

## v1.2.0 (2026-08-05) - Advanced Orchestration & Intelligence

### Added
- **Task decomposition** — `/api/council/decompose` splits complex prompts into role-based subtasks (Analysis→Hermes, Execution→OpenClaw, Review→Agent Zero) and votes on the combined output
- **Iterative debate** — `/api/council/debate` runs multi-round debates with revision prompts and automatic convergence detection (similarity/CONFIRM)
- **Streaming responses** — `/api/council/ask/stream` emits Server-Sent Events as each agent answers (start → agent → final → done); dashboard has a Stream toggle
- **Async task queue** — prioritized background tasks (`/api/tasks*`) for ask/decompose/debate with status tracking and cancellation
- **Audit trail** — JSONL request log with per-agent timing, request IDs, consensus rate and latency analytics (`/api/audit*`)
- **TF-IDF full-text search** — pure-stdlib index over journal + shared docs (`/api/search*`)
- **Semantic result cache** — TTL + size-capped cache for council asks (`/api/cache*`), hit/miss counters on `/api/status`
- **Encrypted secrets vault** — Fernet (AES) when available, HMAC-SHA256-CTR stdlib fallback; masked hints, never stores plaintext (`/api/secrets*`)
- **Memory injection (RAG-lite)** — relevant journal/knowledge/vector context is injected into prompts ≥ 20 chars (config `council.memory_injection`)
- **Terminal command guard** — `rm -rf /`, `mkfs`, `dd`, fork bombs, shutdown etc. are blocked before reaching the PTY; `!force` / allowlist overrides
- **Scheduler v2** — automatic daily backup at 04:00; queue stats in `/api/scheduler/status`
- **Dashboard** — Tasks tab, Intelligence tab (search/cache/audit), Stream toggle, Debate/Decompose buttons
- 13 new tests (total 50 passing)

### Fixed
- `get_secret` decryption bug (wrapper vs payload dict)
- Terminal guard now also covers text-frame input, not only binary keystrokes

## v1.3.0 (2026-08-05) - One-command setup with automatic agent download

### Added
- `./scripts/setup.sh` — one-command setup: Python env + package, **downloads the 3 agents automatically** (Hermes, OpenClaw, Agent Zero from their official repos), installs their dependencies, runs the tests, prints final agent status; `--skip-agents` / `--skip-tests` flags
- `install.sh` — one-liner installer (`curl | bash`), clones to `~/councilkey-os` and runs the full setup
- `councilkey agents` CLI: `status` (installed/running/ports), `install` (clone + deps with step-by-step report), `start` (best-effort launcher + per-agent start hints)
- `GET /api/agents/prereqs` endpoint; `install_agent` task kind for the background queue
- Fresh agent venvs now upgrade pip/setuptools/wheel before installing requirements (fixes upstream `metadata-generation-failed`), with a `.council-installed` marker to skip completed installs
- 7 new tests (total 57 passing)

### Behavior change
- Setup now downloads the agents for you — before, only the build scripts for USB images fetched them and users had to install them later (or run in mock mode)

## v1.4.0 (2026-08-05) - Agents that actually work

### The problem fixed
The dashboard showed 3 agents but none of them answered: the external agent
repos (Hermes/OpenClaw/Agent Zero) were cloned but their gateways never ran
(they are CLIs, not HTTP servers on fixed ports - and OpenClaw's cloned source
tree was unbuilt, which is exactly why `openclaw` failed in PowerShell).

### What changed
- **Local-LLM role agents (new default brain)**: the 3 council roles run on a
  local Ollama model with distinct system prompts (Hermes=analysis,
  OpenClaw=execution, Agent Zero=review). Real local inference, offline, no
  API keys. Fallback chain per agent: external gateway -> local LLM -> explicit
  mock (never silently wrong).
- `councilkey llm status|install|pull` - install Ollama (incl. `winget` on
  Windows) and pull qwen2.5:3b
- `councilkey agents verify` - real smoke test per agent showing the active backend
- **OpenClaw**: `agents install openclaw` now also installs the prebuilt
  `openclaw@latest` CLI globally (fixes "missing dist/entry.mjs")
- **Windows**: `scripts/setup.ps1` + `scripts/start.ps1` (native PowerShell,
  winget for Ollama), fixed `start.bat` with clear errors
- `scripts/dev/llm-demo-server.py` - dev-only Ollama-compatible fixture for CI/sandbox testing (clearly labeled; not part of the product)
- Dashboard Agents tab shows the real per-agent backend + LLM badge in header
- `COUNCIL_HERMES_URL` / `COUNCIL_OPENCLAW_URL` / `COUNCIL_AGENTZERO_URL` env
  overrides for external gateways
- 9 new tests (66 total passing)

### Verified end-to-end in a live server
`councilkey agents verify` -> all 3 agents answer as local-llm with distinct
role voices; `/api/status` reports mode per agent; council ask returns 3 real
answers + vote + journal.

## v1.4.1 (2026-08-05) - Professional visuals + polish

### Added
- Dashboard: SVG favicon (data URI, no file deps) + SEO/OpenGraph meta tags

### Reverted
- The AI-generated visual set (logo/hero/council-flow/privacy/local-ai/
  council-chamber + SVG diagram) was removed per maintainer preference —
  the original image set is kept and used everywhere

### Fixed (debug pass)
- `/3d` route serves the HTML directly (removed fragile endpoint lookup)
- Removed dead `AGENT_PORTS` constant
- `installed_models()` cached 10s (was an extra HTTP call per agent ask)
- Demo server moved out of the product to `scripts/dev/` (dev-only fixture)

### Verified
- 67 tests passing · ruff clean · all 53 modules import · shell syntax OK
- Endpoint sweep 65/65 → 200 · integration 14/14 (roles, decompose, debate,
  SSE, WS chat, terminal guard, cache, tasks, audit)
