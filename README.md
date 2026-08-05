# CouncilKey-Os 🗝️

**A self-contained AI council that runs from a USB stick.** Three local agent gateways (Hermes, OpenClaw, Agent Zero) debate and vote on every request, with smart storage that keeps distilled knowledge and discards raw caches on unplug.

```
pip install -e .
councilkey serve          # dashboard + API on http://0.0.0.0:8443
```

| | |
|---|---|
| Python | 3.11+ |
| Stack | FastAPI, Uvicorn, httpx, Pydantic |
| Agents | Hermes (memory), OpenClaw (action), Agent Zero (builder) |
| Voting | majority · weighted · LLM judge · hermes decides |
| License | MIT |

## Features

- **Council workflow** — every prompt is answered by all three agents, voted on, and journaled. Works *together* (debate + vote) or *alone* (single agent, faster).
- **No traces** — all data lives under `COUNCIL_HOME` (default `/var/lib/council`) with a keep/cache split; heavy caches are flushed on unplug. Verified by `scripts/verify-no-traces.sh` (7 checks).
- **Local-first LLMs** — optional Ollama integration: model management (`pull` / `ensure` / `delete` / `show`), chat, embeddings, and a built-in LLM judge strategy.
- **Knowledge & memory** — LanceDB vector store (offline deterministic embeddings), JSON knowledge graph with search, nightly memory consolidation, self-reflection, evolving skills.
- **Workspaces** — sandboxed canvas file browser (path-confined to `COUNCIL_HOME`), WebSocket terminal (PTY, event-driven), browser fetch with HTML→text extraction.
- **Vision & voice** — desktop screenshots + local vision-model analysis (llava / qwen2.5vl), TTS (Edge free default, ElevenLabs, OpenAI) and local Whisper transcription.
- **Operations** — `councilkey` CLI (`serve`, `doctor`, `storage`, `version`), systemd unit, bootc/live-ISO/portable build scripts, backup create/restore, storage audit & optimize, optional API-key auth, rate limiting, request logging.
- **Dashboard** — 8-tab web UI: council chat with live voting bars, agent status (live probe), storage tools, journal, terminal, secrets, 3D knowledge-graph view, vision/voice panel.

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

## Quick start

```bash
# clone & install
git clone https://github.com/Nikhil009988/CouncilKey-Os.git
cd CouncilKey-Os
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# run the server (dashboard + API)
.venv/bin/councilkey serve

# open http://localhost:8443
```

The council works out of the box: when an agent gateway is offline it degrades to a mock response so the pipeline is always testable. Point `HERMES_TOKEN` / `OPENCLAW_TOKEN` or the gateway URLs to real agents for live operation (see [docs/API.md](docs/API.md)).

### CLI

```
councilkey serve [--host 0.0.0.0] [--port 8443]
councilkey doctor                     # environment health report
councilkey storage [--dry-run]        # audit / optimize storage
councilkey version
```

### systemd

```bash
sudo ./deploy/install.sh              # installs to /opt/councilkey + enables service
```

## API

~45 endpoints under `/api` — health, status, council ask/vote, journal & chat history, storage, backups, config, embeddings, Ollama, knowledge graph, skills, memory, vision, voice, canvas, browser, metrics, update check. Full reference: [docs/API.md](docs/API.md). Interactive docs at `/docs` when running.

Optional auth: set `COUNCIL_API_KEY` (all routes except `/` and `/api/health` require `Authorization: Bearer <key>`); `COUNCIL_RATE_LIMIT` per-IP request limiting; `COUNCIL_CORS` for allowed origins.

## Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Security](docs/SECURITY.md)
- [Build guide](docs/guides/BUILD.md) · [Easy setup](docs/guides/EASY_SETUP_GUIDE.md) · [Pendrive guide](docs/guides/PENDRIVE_GUIDE.md) · [Single binary](docs/guides/SINGLE_BINARY_GUIDE.md) · [Collaboration modes](docs/guides/COLLABORATION_MODES.md)
- [Changelog](docs/CHANGELOG.md)

## Development

```bash
make test        # pytest
make lint        # ruff
.venv/bin/python -m ruff check council tests scripts
```

## License

[MIT](LICENSE)
