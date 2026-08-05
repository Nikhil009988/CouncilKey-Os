# CouncilKey-Os Advanced Smart 5GB Initial - Born Smart, Not Empty

**Goal:** 3 agents live on pendrive with **at least 5GB initial smart data** that makes them much smarter from day 1, not empty learning slowly. Optimized and advanced.

---

## Why 5GB Initial Matters (Not Just 100MB Keep)

Current design: Keep 100-300MB after 1 year of daily use (SOUL, MEMORY, skills custom, knowledge custom, solutions). That's distilled knowledge from raw sessions.

But user wants **5GB initial from day 1** so agents are already smart, not empty.

**What should 5GB contain to make 3 agents much smarter?**

Think like human brain at birth: Not empty, has innate knowledge + language + motor skills + 5GB of curated "pre-training" before life experiences.

For CouncilKey-Os 5GB, we need:

1. **Local LLM Models Offline (4GB) - Biggest Smart**
   - Pendrive OS must work offline without internet (like Reefy LAN offline mode). No API keys needed for basic smart.
   - Ollama qwen2.5:7b = 4.7GB - best balance size/smart: 7B params, 32k context, tool calling, coding, reasoning good
   - Alternative: qwen2.5:3b 1.9GB + deepseek-coder:1.3b 0.8GB + nomic-embed-text 274MB = 3GB total for 3 models specialized
   - We choose: **qwen2.5:7b 4.7GB + nomic-embed-text 274MB = 5GB** shared across 3 agents, all agents use same Ollama server
   - For council: Hermes uses 7b for memory/learning, OpenClaw uses 7b for action/exec, Agent Zero uses 7b for code + coder model if needed

2. **Embeddings + Vector DB (500MB) - RAG Smart**
   - nomic-embed-text 274MB already in 5GB
   - LanceDB or FAISS index pre-built with embeddings of all knowledge/skills/solutions - 200MB
   - FTS5 SQLite pre-indexed MEMORY.md + USER.md + all skills for fast search like Hermes does
   - Total: ~500MB for embeddings + vector DB

3. **Curated Skills (300MB) - Procedural Smart**
   - Hermes: 50+ curated skills: web-dev, debugging, security-audit, devops, system-optimization, council-voting, storage-optimizer, backup-restore, etc. Each skill SKILL.md ~10KB-100KB with YAML frontmatter + detailed how-to + related_skills links for learning_graph
   - OpenClaw: 50+ action skills: file-ops, shell, browser automation via Camofox, deployment, Telegram/Discord/WhatsApp bridge, etc.
   - Agent Zero: 20+ extensions custom + plugins list
   - Shared: 30+ shared skills: council-debate, council-vote, offline-llm, pendrive-optimize
   - Total: ~300MB for 130+ skills (each 10KB-5MB with assets)

4. **Curated Knowledge (300MB) - Declarative Smart**
   - Agent Zero knowledge/custom/ 500+ files organized: linux/, security/, devops/, programming/, council/, networking/, etc. Each .md with curated knowledge
   - Hermes MEMORY.md pre-filled with 1000 curated facts about Linux, security, dev, council voting, pendrive OS, storage optimization (not empty)
   - OpenClaw data/memory.db distilled pre-populated with 500 common actions
   - Shared memory.md cross-agent 1000 facts
   - Total: ~300MB

5. **Solutions (200MB) - Episodic Smart**
   - Agent Zero solutions/ 100+ solutions for common tasks: build-website, debug, optimize-storage, backup-restore, deploy, etc. Each solution is code + docs that agent memorized to solve faster next time (from README: persistent memory allowing to memorize previous solutions)
   - Total: ~200MB

6. **Prompts + Configs + Learning Graph (100MB)**
   - Agents custom prompts: agents/custom/ with optimized system prompts for council roles (Sage memory, Executor action, Builder code)
   - Learning graph: skill nodes with use_count, last_activity, related_skills, pinned, created_by
   - Configs: config.yaml, council.yaml optimized for council debate mode majority 2/3, storage keep smart 5GB + delete heavy 1-10GB
   - Total: ~100MB

**Total: 4.7GB (qwen2.5:7b) + 0.274GB (nomic-embed) + 0.5GB (embeddings+vector DB) + 0.3GB (skills) + 0.3GB (knowledge) + 0.2GB (solutions) + 0.1GB (prompts) ~ 6.4GB raw, with squashfs xz compression ~ 3-4GB compressed, plus RO binaries Node Python agents code ~1GB = 5GB initial goal achievable**

We can tune: Use qwen2.5:3b 1.9GB instead of 7b to fit exactly 5GB with more knowledge/skills, or use 7b and accept 6GB initial but compressed to 5GB.

For this design, we target **5GB initial = 3GB models (qwen2.5:3b 1.9GB + deepseek-coder 1.3b + nomic-embed 274MB = 3.5GB) + 1.5GB knowledge/skills/solutions/prompts/embeddings DB = 5GB**. User can switch to 7b model for 6.5GB if want smarter but larger.

---

## 5GB Smart Initial Structure (RO Squashfs, Not Persistence Wear)

**In LIVE squashfs at `/opt/council/smart-initial/` (RO, no wear, immutable, compressed xz):**

```
/opt/council/smart-initial/
├── models/
│   ├── ollama/
│   │   ├── qwen2.5-3b/  (1.9GB)
│   │   │   ├── modelfile
│   │   │   └── blobs/ (gguf)
│   │   ├── deepseek-coder-1.3b/ (0.8GB)
│   │   └── nomic-embed-text/ (274MB)
│   └── embeddings_cache/
│       └── embeddings.db (200MB pre-computed)
├── hermes/
│   ├── MEMORY.md (pre-filled 1000 facts, 200KB)
│   ├── USER.md template
│   ├── SOUL.md optimized for Sage memory role
│   ├── config.yaml optimized
│   ├── skills/ 50+ curated
│   │   ├── web-dev/SKILL.md (10KB + assets)
│   │   ├── debugging/SKILL.md
│   │   ├── security-audit/SKILL.md
│   │   ├── system-optimization/SKILL.md
│   │   ├── council-voting/SKILL.md
│   │   ├── storage-optimizer/SKILL.md
│   │   ├── backup-restore/SKILL.md
│   │   └── .usage.json (pre-filled use_count, pinned, related_skills)
│   └── learning_graph.json (skill nodes with related_skills links)
├── openclaw/
│   ├── soul.md optimized Executor
│   ├── MEMORY.md distilled 500 actions pre-filled
│   ├── skills/ 50+ action skills
│   │   ├── file-ops/SKILL.md
│   │   ├── shell/SKILL.md
│   │   ├── browser/SKILL.md
│   │   ├── deployment/SKILL.md
│   │   └── telegram-bridge/SKILL.md
│   └── extensions/ pre-installed
├── agent-zero/
│   ├── knowledge/custom/ 500+ files organized
│   │   ├── linux/ 100 files (commands, filesystem, networking)
│   │   ├── security/ 100 files (best practices, hardening, audit)
│   │   ├── devops/ 100 files (docker, k8s, systemd, bootc)
│   │   ├── programming/ 100 files (python, js, go, rust patterns)
│   │   ├── council/ 50 files (council OS architecture, voting, storage)
│   │   └── networking/ 50 files (tailscale, mDNS, LAN offline)
│   ├── solutions/ 100+ solutions
│   │   ├── build-website/
│   │   │   ├── main.py
│   │   │   └── README.md
│   │   ├── debug/
│   │   ├── optimize-storage/
│   │   ├── backup-restore/
│   │   └── deploy/
│   ├── agents/custom/ prompts optimized for Builder role
│   │   ├── agent0.yaml
│   │   └── prompts/
│   │       ├── agent.system.main.role.md (Builder transparent)
│   │       └── agent.system.main.specifics.md
│   └── extensions/custom/ 20+ custom extensions
├── shared/
│   ├── memory.md 1000 facts cross-agent
│   ├── skills/ 30+ shared skills
│   │   ├── council-debate/SKILL.md
│   │   ├── council-vote/SKILL.md
│   │   ├── offline-llm/SKILL.md
│   │   └── pendrive-optimize/SKILL.md
│   └── journal/ initial 10 decisions
├── vector-db/
│   ├── lancedb/ (200MB) pre-built embeddings of all knowledge/skills/solutions for RAG
│   ├── faiss/ alternative
│   └── fts5.db (100MB) pre-indexed MEMORY.md + skills for fast search like Hermes FTS5
└── prompts/
    └── system/ optimized system prompts for council roles
```

**Plus RO binaries (already in LIVE squashfs, 1GB):**
- Node.js 22.14 Linux x64
- Python 3.11 + uv + venvs for hermes, agent-zero, council-core
- Hermes agent code + OpenClaw code + Agent Zero code
- Ollama binary

**Total RO LIVE squashfs: 5GB smart initial + 1GB binaries = 6GB raw, xz compressed to ~3-4GB ISO (like Ubuntu live ISO 4-8GB is normal)**

**Persistence LUKS still only Keep smart 100-300MB after 1 year + 5GB RO initial = 5.3GB total smart on pendrive, Cache RAM 1-10GB auto delete on unplug still same**

---

## How 5GB Makes Agents Much Smarter From Day 1 (Not Empty)

**Before (empty):** User asks "Build website" -> Hermes has no MEMORY.md, no web-dev skill, must create skill from scratch via background_review after conversation, takes N turns, slow.

**After (5GB smart initial):**

- Hermes already has `skills/web-dev/SKILL.md` curated with how to build minimal website, related_skills: [debugging, deployment, security-audit], use_count: 50 (pre-filled), pinned: true
- Hermes MEMORY.md already has 1000 facts: "User prefers minimal design", "Council voting majority 2/3", "Storage keep smart vs delete heavy", etc.
- Hermes can answer immediately with context, not need to learn from scratch

- OpenClaw already has `skills/file-ops/SKILL.md` + `skills/deployment/SKILL.md`, soul.md optimized for Executor, can act immediately

- Agent Zero already has `knowledge/custom/programming/` with web dev patterns, `solutions/build-website/` with main.py + README that it memorized to solve faster next time (from README: persistent memory allowing to memorize previous solutions), so it can write code immediately, not write from scratch

- Shared `vector-db/lancedb/` pre-built embeddings: When user asks, council does RAG search over 500 knowledge + 130 skills + 100 solutions via embeddings, finds relevant, uses as context, much smarter than empty

- Local LLM `qwen2.5:3b` + `deepseek-coder:1.3b` offline: No API key needed, works offline on pendrive without internet, like Reefy offline LAN mode, but smart. User can still add API keys for Claude/GPT for even smarter, but fallback local model works.

- All 3 agents share same Ollama server on `http://localhost:11434`, council orchestrator can call Ollama for LLM Judge voting without API keys

**Result:** 5GB initial = Born smart, not empty. Day 1 already has 130 skills, 500 knowledge, 100 solutions, 1000 memory facts, local LLM offline, vector DB RAG. Then daily use adds more MEMORY.md + skills + solutions via learning loop, keep grows 100-300MB/year on top of 5GB initial.

---

## Storage Optimization for 5GB Initial (Advanced)

**Problem:** 5GB initial on pendrive USB wear if in persistence RW.

**Solution:** 5GB initial in RO squashfs LIVE partition (ISO9660 or squashfs), not persistence RW. RO = no wear, immutable, compressed xz, A/B rollback like bootc.

- **LIVE squashfs:** 6GB raw (5GB smart +1GB binaries) xz compressed to 3-4GB ISO, RO, no wear, 15s boot optimized like Reefy kernel 6.18.40 + systemd critical-chain, no package manager on device
- **PERSIST LUKS ext4:** Only Keep smart 100-300MB after 1 year daily learning, not 5GB. So wear minimal (100-300MB writes/year, not 5GB). Use noatime,commit=60,discard for wear leveling, or f2fs for better USB wear
- **CACHE RAM tmpfs:** 1-10GB heavy sessions/logs/cache in /tmp/council/* tmpfs RAM (no USB wear), auto delete on unplug, cleanup service deletes leaked cache + syncs keep

**Build Process for 5GB Smart Initial:**

1. **Prepare smart-initial/ directory** with structure above
2. **Generate curated knowledge:**
   - `scripts/generate-knowledge.sh` - creates 500 .md files in knowledge/custom/ organized linux/security/devops/programming/council/networking from templates + curated sources
   - `scripts/generate-skills.sh` - creates 130 skills SKILL.md with YAML frontmatter name, category, related_skills, use_count, etc. from templates
   - `scripts/generate-solutions.sh` - creates 100 solutions main.py + README from templates
   - `scripts/generate-memory.sh` - creates MEMORY.md pre-filled 1000 facts + USER.md template + SOUL.md optimized
3. **Download models:**
   - `scripts/download-models.sh` - ollama pull qwen2.5:3b (1.9GB) + deepseek-coder:1.3b (0.8GB) + nomic-embed-text (274MB) into smart-initial/models/ollama/ - needs internet, 5GB download, or use existing cached models
   - If no internet or to keep repo small, create placeholder README.md with instructions to download models and add to payload
4. **Build embeddings DB:**
   - `scripts/build-embeddings.sh` - uses nomic-embed-text to embed all knowledge/skills/solutions into LanceDB or FAISS, creates vector-db/lancedb/ 200MB + fts5.db 100MB pre-indexed
   - Needs python + sentence-transformers or ollama embeddings API
5. **Copy to LIVE chroot:**
   - In `scripts/build-live-iso.sh`, after debootstrap and before mksquashfs, copy smart-initial/ to chroot/opt/council/smart-initial/ (RO)
   - Also copy Ollama binary to chroot/usr/bin/ollama + setup systemd ollama.service
6. **mksquashfs with xz compression:**
   - `mksquashfs chroot image/casper/filesystem.squashfs -comp xz -Xbcj x86 -b 1M` - xz with bcj filter for x86 binaries, 1M block size for better compression, 6GB raw -> 3-4GB compressed
   - This is production grade like Ubuntu live ISO

**Result ISO:** 3-4GB compressed ISO containing 5GB smart initial +1GB binaries + Ubuntu base ~2GB = total ISO 4-8GB normal (Ubuntu 24.04 ISO is ~6GB)

**On Boot:**
- Kernel mounts squashfs RO
- Ollama service starts, loads models from /opt/council/smart-initial/models/ollama/ (RO, but ollama needs RW for blobs? We symlink blobs to /var/lib/council/ollama/ or use /tmp for model cache? Actually Ollama models can be RO if we set OLLAMA_MODELS=/opt/council/smart-initial/models/ollama and make it read-only, Ollama supports RO models dir)
- Council agents: HERMES_HOME=/var/lib/council/hermes/real_home with keep/ -> persistence LUKS + smart-initial/hermes/ RO overlay via bind mount? For 5GB initial, we need overlayfs: lowerdir=smart-initial/hermes (RO) + upperdir=keep/ (RW persistence) + workdir + merged=real_home. This way agents see both 5GB initial RO + daily learned RW.
- Similarly for openclaw and agent-zero
- Dashboard shows smart initial: 5GB RO + 100-300MB RW keep + 1-10GB RAM cache

**Advanced: OverlayFS for Smart Initial + Daily Learning:**

```
/opt/council/smart-initial/hermes/ (RO, 5GB part)
  ├── MEMORY.md (1000 facts pre-filled)
  ├── skills/ 50 curated

/var/lib/council/hermes/keep/ (RW LUKS persistence, daily learning)
  ├── MEMORY.md (additional facts learned daily, overlay upper)
  ├── skills/ (additional skills created daily)

Merged via overlayfs at /var/lib/council/hermes/real_home/
  Lower: smart-initial/hermes/
  Upper: keep/
  Work: keep/.work/
  Merged: real_home/ (what HERMES_HOME points to)

Result: Agent sees both 5GB initial RO + daily RW learning as one dir, like Docker overlay
```

This is advanced and production grade.

---

## Implementation Steps Now

1. Create `scripts/generate-smart-initial.sh` that generates 500 knowledge, 130 skills, 100 solutions, MEMORY.md 1000 facts, etc. from templates (no internet needed, uses local templates)

2. Create `scripts/download-models.sh` that downloads Ollama models qwen2.5:3b + deepseek-coder:1.3b + nomic-embed-text to reach 5GB (needs internet, but can be optional)

3. Create `scripts/build-embeddings.sh` that builds vector DB LanceDB/FAISS + FTS5 from knowledge/skills/solutions

4. Update `builder/live/council-storage-setup.sh` to handle overlayfs for smart-initial + keep

5. Update `scripts/build-live-iso.sh` to copy smart-initial/ to chroot/opt/council/smart-initial/ and setup overlayfs

6. Update `Makefile` with `build-smart-initial` target

7. Update dashboard to show 5GB smart initial + daily keep + cache RAM

We will implement prototype with 100MB of curated knowledge to demonstrate 5GB structure, with instructions to scale to 5GB via Ollama models.

For this commit, we will create:

- `council/smart-initial/` structure with sample curated content (not full 5GB to keep repo small, but structure + 100MB sample + README how to reach 5GB)
- `scripts/generate-smart-initial.sh`
- `scripts/download-models.sh`
- `scripts/build-embeddings.sh`
- `builder/live/smart-payload/` 
- Update `Makefile`
- Update `PENDRIVE_GUIDE.md` with 5GB smart initial

Let's build.
