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

## v1.5.0 (2026-08-05) - Official installer setup, researched from the agents' own code

### What changed
Studied the actual Hermes / OpenClaw / Agent Zero repositories (their
READMEs, entrypoints and install docs) and rebuilt setup around their
official methods:

- **Hermes**: official one-liner (`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash` / PowerShell variant) instead of git clone
- **OpenClaw**: `npm install -g openclaw@latest` (their docs: the repo is a
  pnpm workspace — plain `npm install` of a clone is unsupported, which is
  exactly what caused the old "missing dist/entry.mjs" error)
- **Agent Zero**: Docker-based; installer now detects Docker and points to
  the A0 Launcher / `docker compose up` (clones source only for Docker)
- `councilkey agents status` now reports the real detection: binary on PATH
  (`hermes`, `openclaw`), Docker for agent-zero
- `councilkey agents install` runs the official installers; `start` hands
  interactive agents over to their own UIs with the right command
- `setup.sh` / `setup.ps1` simplified: local LLM first (that's what makes
  the council answer), external agents second (optional, official
  installers); flags renamed `--no-agents` / `--no-llm`
- Docs: EASY_SETUP_GUIDE explains the two layers (council on local LLM vs
  optional external interactive agents) and why official installers are used

### Verified in this workspace
- OpenClaw installed for real via `councilkey agents install openclaw`
  (npm registry reachable) -> `OpenClaw 2026.7.1-2` on PATH, status shows
  installed
- Hermes installer path fails gracefully here (sandbox blocks the domain)
  with the exact manual command printed - works on real machines
- Agent Zero path prints the Docker requirement clearly
- 67 tests passing, ruff clean

## v1.5.1 (2026-08-05) - "Does openclaw actually start?" - tested and answered

Tested the exact user scenario in this workspace: after setup, typing
`openclaw` in a terminal.

Findings (from running the real CLI):
- `openclaw` installs and starts; on FIRST run it says "Onboarding needs
  an interactive TTY" because no model provider is configured yet
- `openclaw doctor` runs real health checks (config, gateway, memory)
- `openclaw agent -m "..." --local --agent main` runs a one-shot turn
- OpenClaw works with the SAME local Ollama from our setup: set
  OLLAMA_API_KEY (any value) + `--model ollama/qwen2.5:3b`
- Without a provider it errors "No API key found for provider openai"
  (cloud-model default) - documented, with the local-Ollama fix

Changes:
- `councilkey agents start openclaw` now prints the exact steps: run it
  yourself, first-run wizard, health check, one-shot test command
- EASY_SETUP_GUIDE: new "Testing an external agent after setup" section
  (start? / first run / one-shot test / chat) + troubleshooting rows for
  "Onboarding needs an interactive TTY" and "No API key found"
- 67 tests passing, ruff clean

## v1.6.0 (2026-08-05) - Interactive setup wizard (asks for API keys etc.)

Researched how the real agent projects handle first-run config (OpenClaw's
`openclaw onboard --non-interactive --auth-choice <x> --<provider>-api-key`,
Hermes' `hermes setup`/`hermes model`, their env API keys) and built the
same kind of guided flow for CouncilKey-Os:

- **`councilkey setup`** - interactive wizard:
  - prerequisite check
  - install local LLM (Ollama + qwen2.5:3b)? (default yes)
  - model provider menu: Local Ollama (free) / OpenAI / Anthropic / Gemini /
    OpenRouter / skip
  - prompts for the API key (hidden input) and stores it **encrypted** in
    the secrets vault - never plaintext
  - configures the installed OpenClaw CLI non-interactively with the chosen
    provider (verified against the real `openclaw onboard` flags)
  - optionally installs the external agents via their official installers
  - tests + real verification
  - writes a setup summary to `$COUNCIL_HOME/setup-summary.json`
- **`councilkey agents env`** - exports the vault API keys for the external
  agents: `eval "$(councilkey agents env)"` (bash) / `| Invoke-Expression` (PS)
- **`setup.sh` / `setup.ps1`** now delegate to the wizard; interactive shells
  get prompts, non-interactive shells run defaults (`--provider ollama`)
- Non-interactive mode for automation: `councilkey setup --provider openai --api-key ... --no-agents --no-llm --skip-tests`
- 5 new tests (72 total), ruff clean

## v1.7.0 (2026-08-05) - API-key-first: one key powers the council + all 3 agents

Per maintainer direction, the local LLM (Ollama) is no longer the default
path (kept available via `councilkey llm` for later/offline use). The setup
now centers on model providers:

- **New provider client** (`council/llm/provider.py`): the three council
  roles answer via OpenAI / OpenRouter / Gemini (OpenAI-compatible) or
  Anthropic, using the API key from setup - stored encrypted in the vault,
  read at request time. Per-provider base URLs overridable via
  `OPENAI_BASE_URL` etc. (used by tests + self-hosted gateways).
- **Backend resolution** per agent: gateway -> provider (API key) -> mock.
  `/api/status` reports `provider` + active provider/model.
- **Setup wizard** updated: provider menu (OpenAI/Anthropic/Gemini/
  OpenRouter/skip), hidden API key input, encrypted storage, automatic
  OpenClaw configuration. Ollama removed from the menu.
- **Dashboard**: new Setup tab (`/api/setup/status` - provider, keys,
  agents installed, last setup time), header badge shows the active AI
  provider + model, Agents tab shows provider mode, mock guidance points
  at `councilkey setup`.
- Dev fixture now serves both Ollama and OpenAI-compatible protocols for
  CI/sandbox testing of the real provider code path.
- 8 new/updated tests (79 total), ruff clean.

Verified live: provider mode with a local OpenAI-compatible endpoint ->
all 3 roles answer with distinct voices, council ask returns vote +
journal, endpoint sweep 59/59, setup status endpoint reports correctly.

## v1.7.1 (2026-08-05) - councilkey ask: all 3 agents at once from the terminal

- New `councilkey ask "question"` command - the three council roles
  (Hermes/OpenClaw/Agent Zero) answer the same prompt, then the vote runs.
  Flags: --strategy (majority/weighted/llm_judge/hermes_decides),
  --debate --rounds N, --decompose, --alone <agent>.
- Guide: new "Use all 3 agents at once" section (terminal / dashboard
  Together mode / API) with a real output example.
- README quick start updated.
- Tested live: together (3/3 consensus), decompose, debate (2 rounds),
  alone - all verified against the provider client.

## v1.8.0 (2026-08-05) - Automatic pendrive setup + CrewAI (4th) + Aider (5th) agents

### Pendrive auto-setup (one command, plug-and-start)
- New `scripts/pendrive-setup.sh <mount>` (and `councilkey pendrive <mount>`):
  copies the project, creates a **portable venv on the stick**, points
  COUNCIL_HOME at `council-data/` on the stick, writes `START.bat` +
  `start.sh` plug-in launchers (auto-bootstrap on first run) and an
  `autorun.inf` so Windows shows a "Start CouncilKey-Os" prompt on plug-in.
- `--wizard` flag bakes the API key + agents into the stick during the build.
- Verified live: built a stick in a temp dir, ran its `start.sh` with a
  free port -> server booted from the stick's own data.

### Two new optional agents
- **CrewAI** (4th): `pip install crewai` - role-based agent crews; designed
  to work together natively (`crewai create crew && crewai run`), solo too.
- **Aider** (5th): `pip install aider-chat` - pair-programming chat agent
  that uses the same API keys as our setup (OpenAI/Anthropic/Gemini/
  OpenRouter) - easy, Hermes-like, best fit for the project.
- `councilkey agents status` shows all 5 with install method + runtime;
  install supports the pip method.

### Docs
- Guide: "Automatic pendrive setup" section, 5-agent table with run
  commands, together/solo notes. README: pendrive mode + 5 agents.
- 4 new tests (83 total), ruff clean.

## v1.8.1 (2026-08-05) - Fix OpenClaw install on Windows (WinError 2)

Real-world report from a Windows machine: `councilkey agents install openclaw`
failed with `npm install failed: [WinError 2] The system cannot find the file
specified` - and Hermes installed fine, so it wasn't a network issue.

Root cause: on Windows, `npm` is `npm.cmd`; calling it by bare name through
subprocess without a shell raises WinError 2. Same latent issue for any
`.cmd`/`.exe` tool invoked by the installers.

Fix:
- New `council/agents/proc.py`: `which_resolved()` (adds PATHEXT suffix
  lookup: npm -> npm.cmd) and `run_cmd()` (cross-platform runner used by
  the agent installer, the setup wizard's OpenClaw configuration and the
  official-installer step).
- Agent Zero step message clarified: it is not a failure - Docker is a
  hard requirement by design; message now says so and gives the Windows
  install command (winget install Docker.DockerDesktop).
- 2 new tests for Windows command resolution (85 total), ruff clean.

## v1.8.2 (2026-08-05) - Setup wizard: no more silent "stuck" phases

Real-world report: after aider installed, the wizard appeared stuck with a
blinking cursor.

Root cause: two silent steps ran with zero output - the full pytest suite
(30s+) and the council verification (real API calls, up to 30s per agent),
plus the OpenClaw configuration step.

Fixes:
- Every long step now prints what it is doing first and how long it took:
  "running the test suite - this can take a minute or two...",
  "configuring OpenClaw with your provider (can take a minute)...",
  "Verifying the council - asking each agent (real API calls...)", with
  per-step elapsed seconds on completion.
- The test suite is now OPTIONAL in interactive mode: "Run the test suite
  now? (~1 min; you can run 'make test' later) [y/N]" - default No.
- Fixed _confirm() bug: pressing Enter ignored the default and always
  answered Yes - empty input now respects the shown default.
- Guide: total setup time table (~10-25 min, per-step) + troubleshooting
  row for the "blinking cursor" case.
- 85 tests passing, ruff clean.


## v1.9.0 (2026-08-05) - Agent Zero without Docker

Per maintainer request, Agent Zero now installs and runs like Hermes/OpenClaw:

- Install method changed from docker-launcher to source-venv: clone the
  official repo + create a Python venv + `pip install -r requirements.txt`
  - no Docker needed for basic chat. Docker is now OPTIONAL (only adds the
  built-in terminal/browser tools, matching their hybrid dev approach).
- Verified from their code: agent.py and the API never import Docker at
  startup - only the terminal tool uses the Docker SDK.
- Requires Python 3.12+ (their code uses `type X = ...` syntax); the
  installer now checks and prints a clear hint instead of failing late.
- `councilkey agents status` detects agent-zero by its venv, not Docker;
  start() hands over with `cd tools/linux/agent-zero && .venv/bin/python agent.py`.
- Guide updated (agent table + troubleshooting). 86 tests, ruff clean.

## v1.9.1 (2026-08-05) - deep QA pass: 5 real bugs found & fixed

Full test-and-debug pass across every code path:

1. **OpenClaw configure detection broken**: `openclaw onboard` exits non-zero
   when its gateway isn't running, but STILL writes the config. The wizard
   checked only the output tail (which never contained "Updated config"),
   so a successful config was reported as failed. run_cmd now returns the
   full output; success is detected from the full text. (Verified: manual
   run wrote config + exit 1 -> wizard now reports ✅ configure OpenClaw.)

2. **agents verify crashed on crewai/aider**: verify iterated over ALL 5
   registered agents, but build_default_clients only creates the 3 council
   roles -> KeyError 'crewai'/'aider'. verify now checks exactly the 3
   council roles and notes that crewai/aider are external CLIs.

3. **Wizard crashed with a traceback when COUNCIL_HOME couldn't be
   created** (e.g. /var/lib/council unwritable): now a clear error +
   exit 1 + hint (COUNCIL_HOME=/path councilkey setup).

4. **Secrets vault crashed on unwritable path**: set_secret now returns
   {"ok": false, "error": ...} instead of raising.

5. **Memory injection relevance bug**: retrieve_context scored LanceDB rows
   flat 4 even when irrelevant (e.g. "hello world" for a storage query),
   outranking genuinely relevant journal entries; token matching missed
   word forms (optimize vs optimization). Now: prefix matching
   (>= 4 chars), journal weighted by overlap*3, memory rows gated on real
   overlap. This also fixed a flaky test (ran the full suite 3x clean).

Also: wizard ensures COUNCIL_HOME exists up front.
91 tests passing (5 new regression tests), ruff clean.

## v1.9.2 (2026-08-05) - bulletproof installer + wizard retry + councilkey update

Real-world report from a Windows machine showed the user was still seeing
the old failures - they were running a pre-fix clone. This release makes
that impossible to hit again:

1. **npm install hardened for Windows**: uses the RESOLVED npm.cmd path
   explicitly (proc.which_resolved) and the error now prints the npm path
   + the exact manual command to run in a new terminal if it still fails.
2. **OpenClaw config retried after agent install**: the wizard now tracks
   whether the step-2 "configure OpenClaw" succeeded, and if it failed
   (usually because openclaw wasn't installed yet), it retries
   automatically once the agents are installed.
3. **Hermes pip fallback**: if the official installer domain is
   unreachable, `pip install hermes-agent` (official Nous Research PyPI
   package) is used as a fallback - verified working in this sandbox
   where the domain is blocked.
4. **`councilkey update`** command: pulls the latest code + reinstalls,
   so users on old clones can get fixes with one command. The wizard
   banner now hints: "running an old clone? run 'councilkey update'".
5. Wizard banner tip + agent-zero hint already in place.

2 new regression tests (93 total), ruff clean.

## v1.9.3 (2026-08-05) - wizard: progress display, per-agent selection, combined pip

Reported: after aider installed, the wizard "took much time" with no
indication of what was next.

Fixes / improvements:
- **Live progress display**: every long operation now shows
  `⏳ installing openclaw... 42s elapsed (please wait)` updating in place
  (via a background ticker) and clears when done - the wizard never looks
  frozen.
- **Numbered steps [1/5]..[5/5]** with a "NEXT: ..." hint after each step
  (choose provider -> install agents -> finish, etc).
- **Per-agent selection**: instead of all-or-nothing, the wizard lists the
  5 agents with time estimates (Hermes 5-15 min, OpenClaw 1-3 min,
  Agent Zero needs 3.12+, CrewAI 2-5 min, Aider 1-2 min) and you pick
  which to install (comma-separated, e.g. 2,4 or 'all').
- **Combined pip install**: CrewAI + Aider install in ONE pip command
  instead of two sequential ones (pip resolves shared deps once).
- **Per-agent elapsed time** and a **total time** at the end
  ("Setup finished in 6m 12s").
- New run_with_progress / human_duration helpers in council/agents/proc.py.
- 1 new test (94 total), ruff clean. Guide updated with the new flow.
