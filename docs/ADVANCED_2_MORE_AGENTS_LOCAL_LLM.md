# Advanced: 2 More Optional Agents + Local LLM + More Smarter

**User Request:** "add more advanced things that make the agents more smarter and give 2 more agents optional if user want he can download and use them too and check local llm option there"

## 1. 2 More Optional Agents (Download If User Wants)

**Core 3 Always (5GB smart initial):**
- Hermes Sage (Memory & Learning)
- OpenClaw Executor (Action & Comms)
- Agent Zero Builder (Code & Transparency)

**Optional 2 More (Download If User Wants, Makes Council 5 Agents):**

### Optional Agent 4: Claude Code (Anthropic) - The Coder

**Why:** Best for coding tasks, from portable-agent-usb project that had Claude Code + Codex CLI.
- **Role:** Coder - Writes, reviews, debugs code, uses LSP, AST-aware, IDE integration
- **Strengths:** Code intelligence (LSP, AST), Claude only but best code model, skill system SKILL.md similar to Hermes, IDE integration VS Code/JetBrains
- **In Council:** When user wants coding, council can delegate to Claude Code alone or include in 5-agent vote for coding tasks
- **Install Size:** ~500MB (Node.js + @anthropic-ai/claude-code npm + dependencies)
- **Port:** 18791 (next after 18789 openclaw, 18790 hermes)
- **Storage Keep:** config/.claude/CLAUDE.md, skills/, .credentials.json (OAuth token saved on USB, like portable-agent-usb)
- **Storage Delete:** tmp, logs, cache
- **How to download:** `council agents install claude-code` or `make download-optional-agents AGENT=claude-code` or dashboard [Download] button

### Optional Agent 5: Codex CLI (OpenAI) + Gemini CLI (Google) Hybrid - The Researcher

**Why:** Best for research, web search, multimodal, plus OpenAI ecosystem. We combine Codex (OpenAI) + Gemini as one research agent, or make them separate but we have limit 2 optional, so we make one hybrid Researcher that can switch between Codex and Gemini.

**Alternative Option:** Actually we can make 2 optional as:
- Agent 4: Claude Code
- Agent 5: Gemini CLI + Codex CLI (Researcher)

Or better for variety:
- Agent 4: Claude Code (Coder)
- Agent 5: Gemini CLI (Researcher) - multimodal, vision, research, web search, 1M context

**We choose:**
- **Optional 4: Claude Code** - Coder
- **Optional 5: Gemini CLI** - Researcher (Research, Web Search, Multimodal Vision, 1M context)

**Agent 5: Gemini CLI - The Researcher Details:**
- **Role:** Researcher - Web search, papers, research, multimodal vision, 1M context, fact checking
- **Strengths:** Gemini 2.5 Flash/Pro, 1M context, multimodal, grounded search, Google ecosystem
- **In Council:** When user wants research, council delegates to Gemini alone, or 5-agent vote for research-heavy tasks
- **Install Size:** ~800MB (Node.js + @google/gemini-cli + Python deps)
- **Port:** 18792
- **Storage Keep:** config/.gemini/, skills, knowledge
- **Storage Delete:** cache, logs
- **Download:** `council agents install gemini-cli`

**Total Optional 2: Claude Code + Gemini CLI = ~1.3GB + Core 3 (5GB) = 6.3GB total if user downloads both optional.**

**Council Voting With Optional:**
- Default: 3 agents core, majority 2/3
- With 1 optional enabled (4 agents): majority 3/4
- With 2 optional enabled (5 agents): majority 3/5 or 4/5 configurable
- User can choose in dashboard or council.yaml: council.mode 3 or 5 agents

**Dashboard:** Agents tab shows Core 3 always online + Optional 2 with [Download] button if not installed, [Enable/Disable] toggle, [Solo] [Together] buttons. When optional installed, council can be 5 agents.

**CLI:**
```bash
council agents list  # Core 3 + Optional 2 (installed or not)
council agents install claude-code  # Downloads Claude Code to tools/optional/claude-code/
council agents install gemini-cli   # Downloads Gemini CLI to tools/optional/gemini-cli/
council agents install all          # Both optional
council agents uninstall claude-code
council ask --mode together --agents 5 "Build website"  # 5 agents council (if optional installed)
council ask --mode alone --agent claude-code "Review my code"
council ask --mode alone --agent gemini-cli "Research quantum computing papers"
```

## 2. Local LLM Advanced - Check Option There

**Current:** We have download-models.sh Option A/B/C with Ollama qwen2.5:3b 1.9GB + deepseek-coder 1.3b 0.8GB + nomic-embed 274MB = 3GB, and build-embeddings.sh for vector DB.

**Advanced Local LLM Production:**

### a. Local LLM Management

**We need to check local LLM option there (in pendrive, dashboard, CLI):**

- **Ollama Server:** Should run as systemd service ollama.service, binds 127.0.0.1:11434, models in /opt/council/smart-initial/models/ollama/ RO + /var/lib/council/ollama/ RW if need to pull new models on pendrive persistence (if internet available, e.g., user plugs pendrive into PC with internet, can pull more models to persistence)
- **Model Management:**
  - `council llm list` -> Lists installed models: qwen2.5:3b, deepseek-coder:1.3b, nomic-embed-text, plus any user pulled models
  - `council llm pull qwen2.5:7b` -> Pulls model to persistence if internet, adds to 5GB smart initial RO? Actually RO can't write, so pull to RW /var/lib/council/ollama/ and overlay
  - `council llm status` -> Ollama server status, models loaded, RAM usage, GPU usage
  - `council llm test qwen2.5:3b "Hello"` -> Test model
  - Dashboard: Local LLM tab shows installed models, size, RAM, Pull new model button, Test

- **Embeddings Advanced:**
  - nomic-embed-text 274MB for RAG
  - LanceDB / FAISS vector DB pre-built 200MB with embeddings of all 500 knowledge + 130 skills + 100 solutions + 1000 MEMORY.md facts
  - FTS5 SQLite pre-indexed for fast search like Hermes
  - Council does RAG: Query embedding via nomic-embed, search LanceDB, find relevant knowledge/skills/solutions, use as context for LLM

- **LLM Judge with Local LLM (No API Keys Needed):**
  - Currently LLM Judge uses LiteLLM with API keys, fallback longest if no key
  - Advanced: Use local Ollama qwen2.5:3b for LLM Judge offline, no API keys needed, works offline like Reefy LAN offline
  - `council ask --mode together --strategy llm_judge --judge-model qwen2.5:3b "prompt"` -> Uses local Ollama to judge best among 3 or 5 agents

- **Multi-Model Council:**
  - Each agent can use different local model:
    - Hermes Sage: qwen2.5:3b (good memory, reasoning)
    - OpenClaw Executor: qwen2.5:3b (action)
    - Agent Zero Builder: deepseek-coder:1.3b (code specialized)
    - Claude Code optional: claude-code uses Claude API but can fallback to deepseek-coder local
    - Gemini CLI optional: gemini-cli uses Gemini API but can fallback to qwen2.5:3b local
  - Config in council.yaml: `llm: {hermes: qwen2.5:3b, openclaw: qwen2.5:3b, agent-zero: deepseek-coder:1.3b, judge: qwen2.5:3b}`

### b. Check Local LLM Option There (In Dashboard + CLI + Pendrive)

**In Dashboard - Local LLM Tab (New Tab 7):**

- Status: Ollama server running on 127.0.0.1:11434, models installed list with size, RAM usage, GPU usage
- Models: qwen2.5:3b 1.9GB (installed), deepseek-coder:1.3b 0.8GB (installed), nomic-embed-text 274MB (installed), plus available to pull: qwen2.5:7b 4.7GB, llama3.1:8b 4.9GB, etc.
- Actions: [Pull Model] button with model name input, [Test] button, [Delete] button
- Embeddings: Vector DB status: LanceDB 200MB with 500 knowledge + 130 skills + 100 solutions embedded, FTS5 100MB, [Rebuild] button calls build-embeddings.sh
- LLM Judge: Select judge model: qwen2.5:3b (local offline), claude-sonnet (API), gpt-4o (API), [Test Judge]
- Offline Mode: Shows if internet available, if not, shows offline mode using local LLM only (like Reefy offline LAN)

**In CLI:**

```bash
council llm list  # Installed models
council llm status  # Ollama server status, RAM, GPU, models loaded
council llm pull qwen2.5:7b  # Pull model to persistence if internet
council llm test qwen2.5:3b "Hello world"  # Test model
council llm embeddings list  # Vector DB status
council llm embeddings rebuild  # Rebuild LanceDB + FTS5 from knowledge/skills/solutions
council llm judge --model qwen2.5:3b  # Set judge model to local offline
council ask --mode together --strategy llm_judge --judge-model qwen2.5:3b "Build website"  # Council with local LLM judge offline, no API keys needed
```

**In Pendrive (On Boot):**

- Ollama service starts automatically via systemd ollama.service (if installed in Live ISO + Bootc)
- Models in RO /opt/council/smart-initial/models/ollama/ + RW /var/lib/council/ollama/ overlay
- If internet available when pendrive plugged into PC with internet, user can pull more models to RW persistence
- If no internet (offline pendrive like Reefy LAN offline), local LLM still works with pre-installed 5GB smart initial models
- Check option there: Dashboard Local LLM tab shows offline mode with local models only, no API keys needed

## 3. More Advanced Things That Make Agents More Smarter

Beyond 5GB smart initial (500 knowledge, 130 skills, 100 solutions, 1000 facts, local LLM), we need more advanced smart features:

### a. Knowledge Graph (Advanced Over Flat Knowledge)

**Current:** 500 knowledge files flat, organized by category folders, RAG via embeddings.

**Advanced:** Build knowledge graph with relationships, like Hermes learning_graph.py but more advanced:

- Nodes: Skills, Memories, Solutions, Knowledge, Users, etc.
- Edges: related_skills, related_knowledge, used_together, created_from, etc.
- Example: Skill web-dev related to debugging, deployment, security-audit; Knowledge linux/filesystem related to security/hardening
- Use: When user asks "Build website", knowledge graph finds not just web-dev skill but also related debugging + deployment + security-audit via graph traversal, much smarter than flat RAG
- Implementation: `council/knowledge/graph.py` builds graph from skills/.usage.json related_skills + learning_graph.json + knowledge custom frontmatter related, stores in `vector-db/knowledge_graph.json` + `knowledge_graph.db` SQLite
- Size: 100MB for graph DB

### b. Memory Consolidation (Nightly Job)

**Current:** Background_review after N turns distills sessions -> MEMORY.md + skills (Hermes pattern).

**Advanced:** Nightly consolidation job (like human sleep consolidates memories):

- Cron job daily 2am: `council-memory-consolidation.service`
- Reads journal/*.md today + sessions/ today (if not deleted) + MEMORY.md + USER.md
- Uses LLM (local Ollama or API) to consolidate: extract new facts, merge duplicates, compress old facts, update MEMORY.md + USER.md + shared/memory.md
- Updates skills/.usage.json use_count, archives unused skills >90d not pinned
- Updates knowledge graph related_skills
- Logs to journal: "Memory consolidation 2026-08-04: 10 new facts, 2 new skills, 1 archived"
- Size: Small, but makes smarter daily

### c. Skill Evolution (Self-Improvement Advanced)

**Current:** Hermes creates new skill after complex task via background_review, use_count tracked in .usage.json.

**Advanced:** Skills evolve based on usage + journal + user feedback:

- Skill versioning: Each skill has version, changelog, previous versions archived
- Skill mutation: learning_mutations.py (from Hermes codebase) mutates skill based on usage: if skill fails often, LLM suggests improvement
- Skill merging: If two skills overlap (e.g., web-dev and deployment overlap 80%), suggest merging into one
- Skill splitting: If one skill too broad (e.g., devops covers docker+k8s+systemd), suggest splitting into 3
- User feedback: Dashboard has 👍👎 buttons for each council response, if 👎, skill that was used gets flagged for improvement
- Implementation: `council/skills/evolution.py` with mutate, merge, split, versioning

### d. Self-Reflection (Agents Review Own Performance)

**Current:** No self-reflection.

**Advanced:** After each council ask + vote, each agent self-reflects:

- Hermes: "Was my memory recall accurate? Did I provide relevant context from MEMORY.md + USER.md? Should I update MEMORY.md with new fact from this prompt?"
- OpenClaw: "Was my action plan safe? Did I check shared/memory.md? Should I update soul.md?"
- Agent Zero: "Was my code correct? Did I use knowledge/custom/ + solutions/? Should I save new solution to solutions/?"
- Implementation: After broadcast_ask + vote, call each agent's self-reflection prompt via LLM, update MEMORY.md, skills/.usage.json, solutions/ if needed
- Logs to journal: "Self-reflection hermes: Updated MEMORY.md with new fact about user prefers minimal design"

### e. Multi-Modal + Vision + Voice (Advanced)

**Current:** Text only.

**Advanced:** Add vision, voice, like Hermes has TTS, transcription, image_gen, vision:

- Vision: Agent Zero Canvas full Linux desktop + browser DOM annotation + screenshot + AT-SPI accessibility tree (from HermesClaw community project computer-use-linux)
- Voice: TTS via ElevenLabs/OpenAI Edge TTS, transcription via Whisper
- Image Gen: FAL, etc.
- Use: User can say "Build website like this screenshot" + voice memo transcription, agent sees screenshot via vision, builds website
- Implementation: Use Hermes toolsets vision, image_gen, tts, but need API keys or local models (Kokoro TTS local, Whisper local)

### f. Tool Use Advanced (Computer Use)

**Current:** Basic tools: terminal, file ops, browser.

**Advanced:** Full computer use like Agent Zero Canvas:

- Full Linux desktop in Canvas: Agent can use real GUI software, terminals, files, desktop apps inside Canvas
- Browser DOM annotation: Click page elements and turn into inspect, change, lift, or review instructions
- Live document cowork: Edit Markdown, Writer, Spreadsheet, Presentation together
- Host-machine bridge via A0 CLI so same agent can work in real local repos
- Implementation: Use Agent Zero webui + plugins, but need to integrate into CouncilKey-Os dashboard as tab

### g. Learning From Journal (Journal Analysis)

**Current:** Journal is git versioned but not analyzed for learning.

**Advanced:** Analyze journal to improve:

- Journal has 100s of council decisions with prompt, responses, votes, final, timestamp, mode solo/together
- Nightly job analyzes journal: Finds patterns: User often asks web-dev, so suggest creating web-dev skill if not exists; User often uses alone mode for hermes research, so suggest hermes as default for research tasks
- Updates MEMORY.md + USER.md + skills/.usage.json + council.yaml mode default
- Dashboard Journal tab has [Analyze Journal] button that runs LLM over journal and suggests improvements

## Implementation Plan Now

1. **Optional 2 Agents:**
   - Create `council/agents/optional/` registry: claude-code.yaml, gemini-cli.yaml with name, role, port, install script, size, description
   - Create `scripts/download-optional-agents.sh` that downloads Claude Code + Gemini CLI to tools/optional/
   - Update `council/orchestrator/agents.py` to support dynamic agents: Core 3 always + Optional 2 if installed + enabled, council voting 3 or 5 agents
   - Update `council/orchestrator/main.py` to have `council agents list|install|uninstall` commands
   - Update dashboard Agents tab to show Core 3 + Optional 2 with Download/Enable/Disable/Solo/Together buttons
   - Update storage optimizer to handle optional agents keep/cache

2. **Local LLM Advanced:**
   - Create `council/llm/manager.py` with list, pull, status, test, embeddings list/rebuild, judge model
   - Create `scripts/check-local-llm.sh` that checks Ollama status, models, RAM, GPU, internet, offline mode
   - Update `council/orchestrator/main.py` to have `council llm list|status|pull|test|embeddings|judge` commands
   - Update dashboard new tab Local LLM with models list, size, RAM, Pull new model button, Test, Embeddings status, LLM Judge select, Offline Mode indicator
   - Update `builder/live/council-storage-setup.sh` to setup Ollama service + models overlayfs RO+RW

3. **Advanced Smart Features:**
   - Create `council/knowledge/graph.py` for knowledge graph builder
   - Create `council/memory/consolidation.py` for nightly memory consolidation cron job
   - Create `council/skills/evolution.py` for skill evolution mutate/merge/split/versioning
   - Create `council/reflection/self.py` for self-reflection after each council ask
   - Create `council/journal/analyzer.py` for journal analysis to improve MEMORY.md etc.
   - Add to Makefile: build-knowledge-graph, memory-consolidation, skill-evolution, journal-analyze

For this commit, we will implement prototype with optional agents registry + download script + local LLM manager + knowledge graph builder + memory consolidation cron + dashboard update, with demo 100MB + instructions to scale to 5GB + 2 optional.

We have limited time but we will create structure + sample + docs.

Let's build.
