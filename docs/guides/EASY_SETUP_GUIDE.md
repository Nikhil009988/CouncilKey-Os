# Complete Setup & Usage Guide

This guide walks a real user from nothing to a working council — the 3 agents
answering with real local AI, no API keys, no cloud.

---

## 1. What you need

| Requirement | Minimum |
|---|---|
| Operating system | Windows 10/11, Linux, macOS |
| Python | 3.11+ (`python --version`) |
| git | any recent version |
| Disk space | ~4 GB free (Ollama + qwen2.5:3b model ≈ 2 GB, agent repos ≈ 1 GB) |
| RAM | 4 GB (8 GB recommended for smooth LLM responses) |
| Internet | only needed **once** during setup (downloads), not afterwards |

Optional but recommended:
- **Node.js 18+** (for the OpenClaw agent CLI) — `node --version`
- **Ollama** will be installed automatically by setup (see below)

---

## 2. Complete setup

### Option A — Windows (PowerShell, one command)

```powershell
git clone https://github.com/Nikhil009988/CouncilKey-Os.git
cd CouncilKey-Os
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

### Option B — Linux / macOS (one command)

```bash
git clone https://github.com/Nikhil009988/CouncilKey-Os.git
cd CouncilKey-Os
./scripts/setup.sh
```

### Option C — one-liner (clones to `~/councilkey-os`)

```bash
curl -fsSL https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/arena/019fd1ec-councilkey-os/install.sh | bash
```

### What setup does (step by step)

`setup.sh` runs the **interactive wizard** (`councilkey setup`) which asks you
exactly what you need:

| Prompt | What it does | Default |
|---|---|---|
| "Choose model provider" | OpenAI · Anthropic · Gemini · OpenRouter · Skip | OpenAI |
| "API key" | Asks for the key (hidden input) and stores it **encrypted** in the secrets vault — used by the 3 council roles AND the external agents (OpenClaw configured automatically) | — |
| "Install the external agents?" | Installs Hermes / OpenClaw / Agent Zero via each project's official installer | No |
| Tests + verify | Runs the test suite, then asks each council role a real question | Yes |

Flags for automation: `councilkey setup --provider openai --api-key sk-... --no-agents --skip-tests`
(or the same flags via `setup.sh`, which detects non-interactive shells).

> If a step fails because of a temporary network problem, just re-run
> `./scripts/setup.sh` — completed steps are skipped.

---

## 3. Start and use it

```bash
./scripts/start.sh          # Linux/macOS        -> http://localhost:8443
scripts\start.bat           # Windows (double-click works)
# or
councilkey serve            # same thing, from anywhere
```

Open **http://localhost:8443** — that's the dashboard.

### Using the dashboard

- **Council tab** — type a question, pick a mode:
  - *Together*: all 3 agents answer, then vote (2/3 consensus by default)
  - *Alone*: one agent, direct and fast (pick which)
  - *Strategy*: majority / weighted / LLM judge / hermes decides
  - Buttons: **Ask Council**, **Debate** (multi-round), **Decompose** (split into subtasks), **Stream** toggle (live answers as they arrive)
- **Agents tab** — live status of the 3 agents and which brain answers:
  - 🟢 gateway = an external agent server is answering
  - 🟡 local-llm = Ollama model is answering (the default)
  - ⚪ mock = nothing available yet (run `councilkey llm pull`)
- **Storage / Journal / Terminal / Secrets / 3D / Vision+Voice / Tasks / Intelligence** — storage tools, past decisions, a guarded terminal, encrypted key storage, the 3D knowledge graph, vision & voice panels, background tasks, and search/cache/audit.

### Using the CLI

```bash
councilkey agents status     # installed? running? which backend?
councilkey agents verify     # asks each agent a real question - proof it works
councilkey agents install    # download/repair an agent (or: install hermes)
councilkey agents start      # best-effort start of an agent's gateway
councilkey llm status        # is Ollama running? which models?
councilkey llm pull          # download the recommended model (qwen2.5:3b)
councilkey llm install       # install Ollama itself (winget on Windows)
councilkey doctor            # full environment health report
councilkey storage           # audit keep/cache storage
```

### Using the API

```bash
curl -X POST http://localhost:8443/api/council/ask \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "plan a 3-day trip to Goa"}'

curl -X POST http://localhost:8443/api/council/debate \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "sqlite vs postgres", "rounds": 3}'

curl http://localhost:8443/api/status        # agents + modes + models
```

---

## 4. How the agents really work

Two layers, and both are real:

### Layer 1 — the council (this is the product)
The three council roles answer via your **model provider** (the API key from
setup) with distinct system prompts:

| Role | Agent | Provider model (default) |
|---|---|---|
| memory & analysis | Hermes | gpt-4o-mini · claude-3-5-haiku · gemini-2.0-flash |
| action & execution | OpenClaw | same provider |
| builder & review | Agent Zero | same provider |

One API key powers all three roles (and the external agents). The key is
stored **encrypted** in the secrets vault. This is what answers in the
dashboard/API. `councilkey agents verify` asks each role a real question and
shows the backend (gateway / provider / mock).

> Local LLM (Ollama) support remains available via `councilkey llm` for
> offline use — it is not part of the default flow.

### Layer 2 — the external agents (optional, interactive tools)
Hermes, OpenClaw and Agent Zero are interactive chat agents with their own
UIs (CLI, messaging platforms, Docker desktop). The council uses them by
name as roles, but you interact with them directly through their own
interfaces. Each is installed with its **official installer**:

| Agent | Official install | Run it |
|---|---|---|
| Hermes | `curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash` (Linux/macOS) · `iex (irm https://hermes-agent.nousresearch.com/install.ps1)` (Windows) | `hermes` → interactive chat · `hermes gateway` → messaging |
| OpenClaw | `npm install -g openclaw@latest` | `openclaw onboard --install-daemon` → guided onboarding |
| Agent Zero | Docker + the A0 Launcher (agent-zero.ai) | runs a full Linux desktop in Docker |

`councilkey agents install` runs these official installers for you.
If an external agent exposes an HTTP endpoint, point the council at it with
`COUNCIL_HERMES_URL` / `COUNCIL_OPENCLAW_URL` / `COUNCIL_AGENTZERO_URL` and
it becomes the 🟢 gateway backend for that role.

> Why not clone the repos instead? Their own docs say so: OpenClaw is a
> pnpm workspace (plain `npm install` of the clone is unsupported — that's
> what caused the "missing dist/entry.mjs" error), Hermes ships its own
> installer, and Agent Zero needs Docker. Official installers are the
> supported path for all three.

### Testing an external agent after setup (e.g. OpenClaw)

The external agents are interactive tools, so "does it start?" is the first
check, and "does it answer?" is the second (it needs a model provider).

**1. Does it start?**
```bash
openclaw --version        # -> "OpenClaw 2026.7.1-2 ..." = installed + starts
openclaw doctor           # real health checks + fixes (suggests config)
```

**2. First run - tell it which model to use (one-time wizard):**
```bash
openclaw onboard          # interactive wizard: model provider, workspace, etc.
```
> No API key? OpenClaw works with the same local Ollama you already have
> from setup - just make sure Ollama is running and set `OLLAMA_API_KEY`
> (any value registers the provider):
> ```bash
> export OLLAMA_API_KEY=council
> ```

**3. Quick one-shot test - does it actually answer?**
```bash
openclaw agent -m "reply with exactly: openclaw works" --local --agent main
```
You should see OpenClaw's reply. (Add `--model ollama/qwen2.5:3b` to force
the local model.)

**4. Chat with it:**
```bash
openclaw chat             # terminal chat UI
```
or `openclaw` (bare) after onboarding - it opens the interactive chat.

`councilkey agents start openclaw` prints exactly these steps.

> Why does bare `openclaw` say "Onboarding needs an interactive TTY" on
> first run? OpenClaw has no default model configured until you run
> `openclaw onboard` once. After that it opens chat directly.

## 5. Where your data lives

| What | Where |
|---|---|
| Council home (journal, memory, vault, backups) | `COUNCIL_HOME` — Linux default `/var/lib/council`, Windows default `%LOCALAPPDATA%\CouncilKey` |
| Agent downloads | `tools/linux/` (repo dir, gitignored) |
| Encrypted API keys | `$COUNCIL_HOME/secrets/vault.json` (Fernet/`COUNCIL_MASTER_KEY`) |

Heavy caches live under `$COUNCIL_HOME/*/cache` and are cleaned by
`scripts/verify-no-traces.sh` — distilled knowledge (journal, memory, skills)
is kept.

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `openclaw` fails with "missing dist/entry.mjs" | That error only happens with a source clone (unbuilt pnpm tree). The official package fixes it: `npm install -g openclaw@latest` (setup does this automatically) |
| `openclaw` says "Onboarding needs an interactive TTY" | Normal on first run - it wants the interactive wizard. Run `openclaw onboard` once (in a real terminal), or test with the one-shot: `openclaw agent -m "hi" --local --agent main` |
| `openclaw agent` says "No API key found for provider openai" | It defaults to cloud models. Point it at your local Ollama: `export OLLAMA_API_KEY=council` (any value) + `--model ollama/qwen2.5:3b`, or run `openclaw onboard` to pick a provider |
| Dashboard shows all agents ⚪ mock | No API key configured: run `councilkey setup` and choose a provider |
| Agents answer with `[no API key...]` | The key wasn't stored - run `councilkey setup` again, or `councilkey agents env` to check |
| `provider error: 401/403` | The API key is wrong/expired - re-run `councilkey setup` with a valid key |
| `provider error: TLS/SSL` | No internet to the provider, or a custom `*_BASE_URL` is unreachable |
| Hermes installer won't download | Run it manually: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash` |
| Agent Zero won't install | It needs Docker — install Docker Desktop, then use the A0 Launcher (agent-zero.ai) |
| `llm pull` fails | Check internet; try a smaller model: `councilkey llm pull qwen2.5:1.5b` |
| Ollama installed but "not running" | Start it: `ollama serve` (Linux/macOS) or the Ollama app (Windows) |
| Port 8443 busy | `COUNCIL_PORT=9000 ./scripts/start.sh` |
| Setup fails mid-download (no internet) | Re-run setup — finished steps are skipped; or `./scripts/setup.sh --skip-agents --no-llm` and install later |
| Agent gateway shows but answers nothing | The gateway URL is wrong — check `COUNCIL_*_URL` and the agent's own README |
| `councilkey` not found | You're not in the project venv — run from the repo: `./scripts/start.sh` or `.venv/bin/councilkey` |
