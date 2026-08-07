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

## 1.5 Automatic pendrive setup — one command, plug-and-start

Build the whole thing onto a USB stick with ONE command:

```bash
./scripts/pendrive-setup.sh /media/USB            # Linux/macOS
# or from anywhere:
councilkey pendrive /media/USB
# Windows (PowerShell):
powershell -ExecutionPolicy Bypass -File scripts\pendrive-setup.ps1 -Path E:\
# or:  .\councilkey.bat pendrive E:\
```

What it puts on the stick:

| On the stick | Purpose |
|---|---|
| `CouncilKey-Os/` | the whole project + a **portable Python venv** (works on PCs without Python) |
| `council-data/` | the council home — **all data stays on the stick** |
| `START.bat` / `start.sh` | **plug-in launchers** — double-click (Win) or `bash start.sh` (Linux), it bootstraps the venv on first run and starts the dashboard automatically |
| `autorun.inf` | Windows shows a **"Start CouncilKey-Os" prompt** when you plug the stick in |

Add `--wizard` to bake in your API key + agents during the build:
```bash
./scripts/pendrive-setup.sh /media/USB --wizard
```

**On any PC afterwards:**
- **Windows**: plug in → click "Start CouncilKey-Os" (or double-click `START.bat`) → dashboard at http://localhost:8443
- **Linux/macOS**: `bash /media/USB/start.sh`

> Why not silent autorun? Windows blocks real autorun from USB for security
> (that's a feature). The autoplay prompt / one double-click is the
> supported equivalent, and it works on any PC without installing anything.

**And the agents? They run from the stick too.**

| Agent | On the stick |
|---|---|
| Council (Hermes/OpenClaw/Codex roles) | answers via your API key - no install at all |
| **Hermes** | installed **into the stick venv** (`pip install hermes-agent`) - `RUN-HERMES.bat` runs it from the stick with `HERMES_HOME` on the stick |
| **OpenClaw** | CLI installed **on the stick** (`tools/openclaw` via npm) - `RUN-OPENCLAW.bat` sets `OPENCLAW_STATE_DIR` + `OPENCLAW_CONFIG_PATH` to `council-data/openclaw` |
| **CrewAI** | installed **into the stick venv** - `RUN-CREWAI.bat` |
| **Aider** | installed **into the stick venv** - `RUN-AIDER.bat` |
| **Codex** | `RUN-CODEX.bat` (npm CLI on the stick - local execution, no Docker) |

**Everything - the app, the venv, the agents and all their data - lives on
the stick.** Rebuild with `./scripts/pendrive-setup.sh /media/USB --wizard`
(or the PowerShell builder on Windows) and the stick is fully self-contained.

### Three ways to use the stick (any agent, or all at once)

| Mode | How | What happens |
|---|---|---|
| **Agent menu** | double-click `AGENTS.bat` (or `bash agents-menu.sh`) | menu: **A = ALL agents + dashboard**, or pick 1–6 (dashboard / OpenClaw / Hermes / CrewAI / Aider / Codex) |
| **Everything at once** | `LAUNCH-ALL.bat` / `launch-all.sh` | starts the dashboard + every installed agent together |
| **Session mode** | `START-SESSION.bat` (or `start-session.sh`) | **clones the code to this PC temporarily** (fast), keeps ALL memory on the stick (`council-data`); `END-SESSION.bat` stops it and **deletes the PC copy** — unplug any time, nothing of yours is on the PC |

The stick also contains **`PENDRIVE-README.txt`** with these instructions, so
a new user who plugs it in can read everything right there.

> **"OpenClaw said it lives on my PC"** — that's the *global* install
> (`npm install -g openclaw@latest`); OpenClaw's default workspace is
> `C:\Users\you\.openclaw`. On the pendrive build, use **`RUN-OPENCLAW.bat`**
> instead of `openclaw` and everything (workspace, config, memory) stays on
> the stick. To redirect an existing install manually:
> ```powershell
> $env:OPENCLAW_STATE_DIR = "E:\council-data\openclaw"
> $env:OPENCLAW_CONFIG_PATH = "E:\council-data\openclaw\openclaw.json"
> openclaw
> ```

---
## 2. Complete setup

### Option A — Windows (PowerShell, one command)

```powershell
git clone https://github.com/Nikhil009988/CouncilKey-Os.git
cd CouncilKey-Os
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

> **Windows-only user?** Everything you need is native PowerShell +
> `councilkey.bat` (use `.\councilkey.bat` with the `.\` prefix). The
> `Makefile`, `deploy/` (systemd service) and `scripts/build-*.sh` are
> Linux/server extras — you can ignore them entirely. The pendrive build
> on Windows uses `scripts\pendrive-setup.ps1`:
> ```powershell
> powershell -ExecutionPolicy Bypass -File scripts\pendrive-setup.ps1 -Path E:\ -Wizard
> # or:  .\councilkey.bat pendrive E:\ --wizard
> ```

### Option B — Linux / macOS (one command)

```bash
git clone https://github.com/Nikhil009988/CouncilKey-Os.git
cd CouncilKey-Os
./scripts/setup.sh
```

### Option C — one-liner (clones to `~/councilkey-os`)

```bash
curl -fsSL https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/install.sh | bash
```

### What setup does (step by step)

`setup.sh` runs the **interactive wizard** (`councilkey setup`) in 5 numbered
steps. Every step shows what's NEXT, and every long operation shows a live
progress line (`⏳ installing openclaw... 42s elapsed (please wait)`) so you
always know it's working:

| Step | What it asks / does |
|---|---|
| **[1/5]** Prerequisites | checks python + git |
| **[2/5]** Provider + API key | choose OpenAI · Anthropic · Gemini · OpenRouter · Skip, enter the key (hidden, stored **encrypted**); OpenClaw configured automatically (retried later if not installed yet) |
| **[3/5]** External agents | **pick which agents** (comma-separated, e.g. `2,4`): 1 Hermes (5-15 min) · 2 OpenClaw (1-3 min) · 3 Codex (1-3 min, npm, no Docker) · 4 CrewAI (2-5 min) · 5 Aider (1-2 min) · 0 none. CrewAI + Aider install together in one pip command |
| **[4/5]** Tests | optional, default skip (`make test` later) |
| **[5/5]** Verify | asks each council role a real question, shows the backend |

Ends with the **total time**: `✅ Setup finished in 6m 12s`.

Flags for automation: `councilkey setup --provider openai --api-key sk-... --no-agents --skip-tests`

### How long does the full setup take?

| Step | Typical time |
|---|---|
| Python env + CouncilKey-Os | ~1 min |
| API key entry | seconds |
| Configure OpenClaw (if installed) | up to 1 min |
| Hermes (official installer: uv, Python, deps) | 5–15 min |
| OpenClaw (`npm install -g openclaw@latest`) | 1–3 min |
| CrewAI (`pip install crewai`) | 2–5 min |
| Aider (`pip install aider-chat`) | 1–2 min |
| Codex | npm `@openai/codex` - local execution, **no Docker** |
| Test suite | ~1 min (skippable - press **n** when asked) |
| Verify (real API calls) | 10–60 s |
| **Total** | **~10–25 min** on a normal connection |

> **"The terminal is just blinking after an install — is it stuck?"** No.
> The wizard prints a message, then runs the real install/command silently
> (npm/pip/uv downloads, tests, API calls) — that's the blinking part.
> Every step now prints what it is doing and how long it took. If a step
> truly hangs forever (more than ~10 min with no message), press Ctrl+C
> and re-run — finished steps are skipped next time.
(or the same flags via `setup.sh`, which detects non-interactive shells).

> If a step fails because of a temporary network problem, just re-run
> `./scripts/setup.sh` — completed steps are skipped.

---

## 3. Start and use it

### 3.1 Start the agents (what runs and how)

Two layers, both started from the same terminal session:

1. **The council (always works once the API key is set)** — the 3 role
   agents answer through your provider. No separate process to start:
   `councilkey serve` (or the dashboard) uses your key automatically.
2. **The external agents (optional, installed in [3/5])** — each is its own
   interactive program. Start them in their own terminal:

| Agent | Start it | What you get |
|---|---|---|
| Hermes | `hermes` | interactive chat (config first: `hermes setup`) |
| OpenClaw | `openclaw` | interactive chat (first run: `openclaw onboard`) |
| Codex | `codex` (or `codex exec "your task"`) | local agent: terminal, file editing, web tools - runs on your PC, no Docker |
| CrewAI | `crewai create crew my_crew && cd my_crew && crewai run` | a crew of role agents working together |
| Aider | `aider` (in a repo) | pair-programming chat — uses the same API key |

> Tip: the external agents are optional — the dashboard's **Council tab**
> already works with just your API key (no agent install needed).

### 3.2 Start the dashboard

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
| builder & review | Codex | same provider |

One API key powers all three roles (and the external agents). The key is
stored **encrypted** in the secrets vault. This is what answers in the
dashboard/API. `councilkey agents verify` asks each role a real question and
shows the backend (gateway / provider / mock).

> Local LLM (Ollama) support remains available via `councilkey llm` for
> offline use — it is not part of the default flow.

### Layer 2 — the external agents (optional, interactive tools)
Hermes, OpenClaw and Codex are interactive chat agents with their own
UIs (CLI, messaging platforms, Docker desktop). The council uses them by
name as roles, but you interact with them directly through their own
interfaces. Each is installed with its **official installer**:

| Agent | Official install | Run it |
|---|---|---|
| Hermes | `curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash` (Linux/macOS) · `iex (irm https://hermes-agent.nousresearch.com/install.ps1)` (Windows) | `hermes` → interactive chat · `hermes gateway` → messaging |
| OpenClaw | `npm install -g openclaw@latest` | `openclaw onboard --install-daemon` → guided onboarding |
| Codex | `npm install -g @openai/codex` (official package) | `codex` - interactive; `codex exec "task"` - one-shot. Terminal, file and web tools run **locally - no Docker**. Works with your OpenAI or OpenRouter key (`councilkey agents configure codex`) |
| **CrewAI** (4th) | `pip install crewai` (official package) | `crewai create crew my_crew && cd my_crew && crewai run` — role-based teams work **together** natively |
| **Aider** (5th) | `pip install aider-chat` (official package) | `aider` — chat with your repo; uses the **same API keys** as our setup (OpenAI/Anthropic/Gemini/OpenRouter) |

CrewAI and Aider are optional, like the others — the council itself works
without them. Together/solo: CrewAI runs a whole crew together by design
(and single agents solo); Aider is a solo pair-programmer that can be one
more voice in your workflow.

`councilkey agents install` runs these official installers for you.
If an external agent exposes an HTTP endpoint, point the council at it with
`COUNCIL_HERMES_URL` / `COUNCIL_OPENCLAW_URL` / `COUNCIL_CODEX_URL` and
it becomes the 🟢 gateway backend for that role.

> Why not clone the repos instead? Their own docs say so: OpenClaw is a
> pnpm workspace (plain `npm install` of the clone is unsupported — that's
> what caused the "missing dist/entry.mjs" error), Hermes ships its own
> installer, and Codex ships as an npm package. Official installers are the
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

## 4.5 Use all 3 agents at once

The whole point of the council: one question, three answers, one vote.
Three ways to do it:

### 1. Terminal — one command (new)
```bash
councilkey ask "plan a 3-day trip to Goa"
```
```
== Council: together (majority) ==
   votes: hermes:approve, openclaw:approve, codex:approve
   - hermes       openai (gpt-4o-mini)           0.4s
   - openclaw     openai (gpt-4o-mini)           0.5s
   - codex        openai (gpt-4o-mini)           0.4s
   consensus: ✅ 3/3

# Council Decision - Consensus 3/3 ✅
## hermes (council-role) ... ## openclaw (council-role) ... ## codex ...
```
Variants:
```bash
councilkey ask "..." --strategy weighted      # weighted voting
councilkey ask "..." --strategy llm_judge     # LLM judge strategy
councilkey ask "..." --debate --rounds 3      # all 3 debate, then vote
councilkey ask "..." --decompose              # split into subtasks, then vote
councilkey ask "..." --alone openclaw         # just one agent
```

### 2. Dashboard — one click
Open http://localhost:8443 → **Council tab**:
- Mode: **Together** (all 3 debate + vote) or Alone (pick one)
- Strategy: majority / weighted / LLM judge / hermes decides
- Buttons: **Ask Council** · **Debate** (multi-round) · **Decompose** (subtasks) · **Stream** toggle
- The voting bars fill live as each agent answers.

### 3. API — one POST
```bash
curl -X POST http://localhost:8443/api/council/ask \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "plan a 3-day trip to Goa", "strategy": "majority"}'
# responses: 3 agents + votes + consensus + final
```

All three hit the same engine: each of the 3 roles (Hermes=analysis,
OpenClaw=execution, Codex=review) answers independently with its own
system prompt, then the council votes (2/3 by default) and journals the
decision.

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
| Wizard looks stuck (blinking cursor after an install) | It's working - installs/tests/API calls print a message first and run silently after. Watch for the next ✅ line; long steps show timing. Tests are skippable (answer **n**) |
| Hermes installer won't download | Run it manually: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash` |
| Codex won't answer | Run `councilkey agents configure codex` - it needs an **OpenAI or OpenRouter** key (Codex speaks the OpenAI protocol; Gemini/Anthropic keys can't drive it). Check the model in the config: `councilkey agents configure codex` shows where it was written |
| `llm pull` fails | Check internet; try a smaller model: `councilkey llm pull qwen2.5:1.5b` |
| Ollama installed but "not running" | Start it: `ollama serve` (Linux/macOS) or the Ollama app (Windows) |
| Port 8443 busy | `COUNCIL_PORT=9000 ./scripts/start.sh` |
| Setup fails mid-download (no internet) | Re-run setup — finished steps are skipped; or `./scripts/setup.sh --no-agents` and install later |
| Agent gateway shows but answers nothing | The gateway URL is wrong — check `COUNCIL_*_URL` and the agent's own README |
| `councilkey` not recognized in PowerShell | Use **`.\councilkey.bat`** (with the `.\` prefix) from the repo root, or `.\.venv\Scripts\councilkey.exe` — the venv's Scripts folder isn't on PATH, and PowerShell won't run files in the current folder without `.\` |
| `git pull` says "Already up to date" but version is old | You're on a leftover branch, not `main`: `git checkout main && git pull` (a fresh clone is already on `main`) |
| **"Found it on this PC, not as a global command... F:\\CouncilKey-Os did not respond quickly"** | You have TWO copies (PC + stick) and something found the PC one, or the stick wasn't mounted/responded slowly. Fix: (1) plug in the stick and confirm its letter: `Get-PSDrive`; (2) verify which copy you're on: `councilkey which` (shows the path) — it must show the stick's path like `F:\CouncilKey-Os`; (3) if it shows a PC path, you ran the PC copy — always use the stick's launchers (`F:\START.bat`, `F:\RUN-OPENCLAW.bat`); (4) rebuild the stick with the latest code: `git pull` then `pendrive-setup.ps1 -Path F:\ -Wizard`; (5) first run on a slow USB can take a few seconds — that's normal |
| **How do I know I'm running from the pendrive?** | Every stick launcher now prints `Running from: F:\` at startup, and `councilkey version` prints `installed at: <path>`. If it says `C:\Users\...`, you ran the PC copy |
