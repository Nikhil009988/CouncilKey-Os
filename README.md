# CouncilKey-Os 🗝️

**Your private AI council.** Three AI agents — Hermes, OpenClaw and Agent Zero — debate every question, vote on the answer, and remember what they learn. Runs on your machine, on a USB stick, or in the cloud — your data stays yours.

<p align="center">
  <img src="images/banner.png" alt="CouncilKey-Os" width="640">
</p>

---

## Quick Start

### 1. Install (one command)

**Windows (PowerShell):**
```powershell
git clone https://github.com/Nikhil009988/CouncilKey-Os.git
cd CouncilKey-Os
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

**Linux / macOS:**
```bash
git clone https://github.com/Nikhil009988/CouncilKey-Os.git
cd CouncilKey-Os
./scripts/setup.sh
```

**Or one-liner (clones to `~/councilkey-os`):**
```bash
curl -fsSL https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/arena/019fd1ec-councilkey-os/install.sh | bash
```

### 2. Run the setup wizard

```
councilkey setup
```

The wizard asks what it needs and stores answers securely:

1. **Model provider** — OpenAI · Anthropic · Gemini · OpenRouter (or skip and configure later)
2. **API key** — asked with hidden input, stored **encrypted** in the secrets vault; one key powers the whole council
3. **External agents** *(optional)* — Hermes, OpenClaw, Agent Zero, CrewAI, Aider via their official installers

> Non-interactive / CI:
> ```bash
> councilkey setup --provider openai --api-key sk-... --no-agents --skip-tests
> ```

### 3. Start & use

```bash
councilkey serve        # dashboard + API on http://localhost:8443
```

```bash
councilkey ask "plan a 3-day trip to Goa"   # ALL 3 agents answer + vote
```

### Pendrive mode (optional)

Put everything on a USB stick with one command — plug into any PC, click **START.bat**, done:

```bash
./scripts/pendrive-setup.sh /media/USB --wizard
```

---

## What is it for?

- **Second opinions, automatically** — one question, three independent answers, a vote
- **Private AI work** — your data on your machine or USB stick, not a cloud server
- **No-trace sessions** — work anywhere, unplug, nothing stays on the host
- **A learning companion** — journals every session, builds a knowledge graph, remembers what it learned
- **Offline-capable** — optional local LLM (Ollama) support via `councilkey llm`

## How it works

```
You ask ──► 3 agents answer ──► council votes ──► journal + memory
              │  Hermes: memory/analysis     │  majority / weighted /
              │  OpenClaw: action/execution  │  LLM judge / hermes decides
              │  Agent Zero: builder/review  │
                                         └──► final answer + reasoning
```

- **Together** — debate + vote (2/3 agreement by default)
- **Alone** — one agent, direct and fast
- **Debate** — multi-round revision with convergence detection
- **Decompose** — complex tasks split into analysis → plan → review

## Features

| Area | What you get |
|---|---|
| **Council core** | ask / alone / debate / decompose, 4 voting strategies, SSE streaming, WebSocket chat, background task queue |
| **Intelligence** | memory injection (RAG-lite), TF-IDF search, knowledge graph, journal + audit analytics, semantic result cache |
| **Security** | encrypted secrets vault, optional API-key auth, rate limiting, terminal command guard, no-traces audit |
| **Agents** | 5 optional external agents (Hermes, OpenClaw, Agent Zero, CrewAI, Aider) via official installers |
| **Workspaces** | sandboxed canvas file browser, guarded WebSocket terminal, browser fetch, vision + voice panels |
| **Portable** | one-command pendrive setup, bootc/live-ISO/portable build scripts, systemd service |

## Gallery

| | |
|---|---|
| ![Banner](images/banner.png) | ![Architecture](images/architecture.png) |
| ![Dashboard](images/dashboard.png) | ![Agents](images/agents.png) |
| ![Storage](images/storage.png) | ![Together vs Alone](images/together-alone.png) |
| ![No Traces](images/no-traces.png) | ![Easy Setup](images/easy-setup.png) |
| ![5GB Smart](images/5gb-smart.png) | ![Optional LLM](images/optional-llm.png) |
| ![Terminal](images/terminal-real.png) | ![LanceDB](images/lancedb-real.png) |
| ![3D Dashboard](images/3d-dashboard.png) | ![Voice Chat](images/voice-chat.png) |
| ![Vision](images/vision-screenshot.png) | ![Browser](images/browser-camofox.png) |
| ![Canvas](images/canvas-desktop.png) | ![Dashboard v4](images/dashboard-neat-v4.png) |

## CLI reference

```
councilkey serve [--host 0.0.0.0] [--port 8443]   start the dashboard + API
councilkey ask "..." [--strategy X] [--debate] [--decompose] [--alone A]
councilkey setup [--provider X] [--api-key K] [--no-agents] [--skip-tests]
councilkey agents status | install | start | env | verify
councilkey pendrive /media/USB [--wizard]          build a USB stick
councilkey llm status | install | pull             optional local LLM (Ollama)
councilkey doctor                                  environment health report
councilkey storage [--dry-run]                     audit / optimize storage
```

Export stored API keys for the external agents:
```bash
eval "$(councilkey agents env)"        # bash/zsh
councilkey agents env | Invoke-Expression   # PowerShell
```

## Documentation

| Topic | Link |
|---|---|
| Complete setup & usage guide (Windows/Linux/macOS, troubleshooting) | [docs/guides/EASY_SETUP_GUIDE.md](docs/guides/EASY_SETUP_GUIDE.md) |
| API reference (all endpoints) | [docs/API.md](docs/API.md) |
| Architecture | [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) |
| Security | [docs/SECURITY.md](docs/SECURITY.md) |
| Pendrive guide | [docs/guides/PENDRIVE_GUIDE.md](docs/guides/PENDRIVE_GUIDE.md) |
| Build guide (USB / ISO / bootc) | [docs/guides/BUILD.md](docs/guides/BUILD.md) |
| Collaboration modes (together / alone) | [docs/guides/COLLABORATION_MODES.md](docs/guides/COLLABORATION_MODES.md) |
| Change history | [docs/CHANGELOG.md](docs/CHANGELOG.md) |
| Roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) |

## Development

```bash
make deps      # install project + dev deps
make test      # pytest (83 tests)
make lint      # ruff
```

Python 3.11+ · MIT License
