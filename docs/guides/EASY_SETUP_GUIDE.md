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

| Step | What happens | Time (first run) |
|---|---|---|
| 1 | Creates a Python venv and installs CouncilKey-Os (`councilkey` CLI) | ~1 min |
| 2 | **Downloads the 3 agents** (Hermes, OpenClaw, Agent Zero) from their official GitHub repos into `tools/linux/` and installs their dependencies (OpenClaw also gets the prebuilt `openclaw` CLI) | 5–15 min |
| 3 | **Installs Ollama** (the local AI server; `winget` on Windows) and **pulls `qwen2.5:3b`** (~1.9 GB) — this is what makes the 3 agents genuinely answer | 5–15 min |
| 4 | Runs the test suite | ~1 min |
| 5 | **Verifies the council** by asking each agent a real question | ~30 s |

Flags if you ever need them: `--skip-agents` (no agent downloads),
`--no-llm` (no Ollama/model), `--skip-tests`.

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

The council has **two ways** for an agent to answer, in priority order:

1. **External agent gateway** (optional, expert mode) — if you run the real
   Hermes / OpenClaw / Agent Zero servers, point the council at them:
   ```bash
   export COUNCIL_HERMES_URL=http://127.0.0.1:18790
   export COUNCIL_OPENCLAW_URL=http://127.0.0.1:18789
   export COUNCIL_AGENTZERO_URL=http://127.0.0.1:50001
   ./scripts/start.sh
   ```
   Each agent's official README documents its own start command; e.g.
   OpenClaw: `openclaw` (prebuilt CLI installed by setup), Hermes:
   `cd tools/linux/hermes && uv run hermes`, Agent Zero:
   `cd tools/linux/agent-zero && python agent.py`.

2. **Local LLM (the default)** — when no gateway answers, Ollama answers with
   a distinct system prompt per role:
   - **Hermes** (memory & analysis) — `qwen2.5:3b`
   - **OpenClaw** (action & execution) — `qwen2.5:3b`
   - **Agent Zero** (builder & review) — `deepseek-coder:1.3b` (falls back to `qwen2.5:3b`)

   This works offline and needs no API keys. `councilkey agents verify` shows
   you exactly which backend each agent is using.

3. **Mock** — only if neither exists. The dashboard and CLI label it honestly
   (`⚪ mock`); it never pretends to be real.

**Verify everything is live:**

```bash
councilkey llm status     # 🟢 running + at least one model listed
councilkey agents verify  # each agent replies with a real answer
```

---

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
| `openclaw` fails with "missing dist/entry.mjs" | The source clone is unbuilt — `npm install -g openclaw@latest` (setup does this automatically) |
| Dashboard shows all agents ⚪ mock | No LLM running: `councilkey llm status` → `councilkey llm install` → `councilkey llm pull` |
| `llm pull` fails | Check internet; try a smaller model: `councilkey llm pull qwen2.5:1.5b` |
| Ollama installed but "not running" | Start it: `ollama serve` (Linux/macOS) or the Ollama app (Windows) |
| Port 8443 busy | `COUNCIL_PORT=9000 ./scripts/start.sh` |
| Setup fails mid-download (no internet) | Re-run setup — finished steps are skipped; or `./scripts/setup.sh --skip-agents --no-llm` and install later |
| Agent gateway shows but answers nothing | The gateway URL is wrong — check `COUNCIL_*_URL` and the agent's own README |
| `councilkey` not found | You're not in the project venv — run from the repo: `./scripts/start.sh` or `.venv/bin/councilkey` |
