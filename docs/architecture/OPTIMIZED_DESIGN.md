# CouncilKey-Os Optimized Design - Smart Pendrive Storage That Learns

## Goal
3 agents live on pendrive:
- Accessible via pendrive when needed (plug → boot → live)
- One dashboard controls all 3 + terminal access
- Store only what makes them smarter daily, auto-delete heavy junk on unplug
- Encrypted safe, no wear on USB

---

## 1. What Actually Makes Agents Smarter? (from STORAGE_AUDIT.md)

### Core Learning Loop Across All 3:

```
Raw Interaction (session, chat history, logs, cache) HEAVY 1-10GB
    ↓ background_review / curator / active-memory distills
Distilled Knowledge (MEMORY.md, USER.md, skills/*.md, knowledge/custom/, solutions/) LIGHT 100-300MB
    ↓ used next time to be smarter
```

So we **KEEP distilled, DELETE raw** on unplug. This is exactly how human brain works: you don't remember every word of conversation, you remember lessons.

### Must Keep (100-300MB after 1 year):

| Category | Hermes | OpenClaw | Agent Zero | Council Shared |
|----------|--------|----------|------------|----------------|
| **Identity** | SOUL.md | soul.md | agents/{profile}/prompts custom | /etc/council/council.yaml |
| **Long-term Memory** | MEMORY.md, USER.md, memories/ | MEMORY.md equivalent, data/memory.db distilled | knowledge/custom/, solutions/ | shared/memory.md, journal/*.md git |
| **Procedural (Skills)** | skills/*.md (curator-managed + user-owned), skills/.usage.json | skills/ custom | extensions/ custom, plugins/ list | shared/skills/ |
| **People** | pairing/ allowed Telegram/Discord users | pairing/ WhatsApp/Telegram pairing | - | - |
| **Automation** | cron/ daily reports | cron/jobs | - | - |
| **Secrets (encrypted)** | .env, auth.json (Nous Portal) | .env, openclaw.json, gateway.token | usr/settings.json (api_keys, secrets, variables) | secrets/ vault |
| **Config** | config.yaml | config | settings.json agent_profile | council.yaml |

### Must Delete on Unplug (1-10GB):

- **sessions/** Hermes session_{sid}.json + sessions.json (90 day history) + FTS5 SQLite
- **data/history** OpenClaw raw conversation LanceDB/DB
- **logs/** all agents
- **image_cache/, audio_cache/** Hermes, cache/ OpenClaw
- **tmp/, workdir/tmp, __pycache__, node_modules/.cache, npm-cache**
- **lsp/bin/** - 100MB+ LSP binaries, can reinstall
- **.venv/** - Python venvs 500MB+ each, should be in RO squashfs ISO not persistence

---

## 2. Optimized Pendrive Layout

### Partition Layout (GPT):

```
/dev/sdX1: EFI 512MB FAT32 LABEL=COUNCIL_EFI (grub, shim)
/dev/sdX2: LIVE 8GB ISO9660/R squashfs LABEL=COUNCIL_LIVE (RO, immutable, contains node+python+agents code)
/dev/sdX3: PERSIST rest LUKS2 encrypted ext4 LABEL=COUNCIL_PERSIST (RW, noatime, commit=60 for wear leveling)
```

### Inside LUKS (Decrypted at /var/lib/council):

```
/var/lib/council/
├── secrets/                     # 700, encrypted at rest via LUKS, also gpg encrypted files
│   ├── hermes.env.gpg           # .env + auth.json gpg
│   ├── openclaw.env.gpg
│   ├── agentzero.settings.gpg
│   └── master.key               # For podman secret
├── hermes/
│   ├── keep/                    # Actually persistence: symlink target for ~/.hermes keep
│   │   ├── SOUL.md
│   │   ├── MEMORY.md
│   │   ├── USER.md
│   │   ├── config.yaml
│   │   ├── skills/              # Only user + curator-managed, not bundled
│   │   │   ├── .usage.json
│   │   │   └── my-skill/SKILL.md
│   │   ├── memories/
│   │   ├── cron/
│   │   ├── pairing/
│   │   └── hooks/
│   └── cache/ -> /tmp/council/hermes/ (tmpfs, deleted on shutdown) symlink: sessions, logs, image_cache, audio_cache, cache
├── openclaw/
│   ├── keep/
│   │   ├── soul.md
│   │   ├── MEMORY.md
│   │   ├── .env (symlink to secrets)
│   │   ├── skills/ (custom only)
│   │   └── pairing/
│   └── cache/ -> /tmp/council/openclaw/ (tmpfs)
├── agent-zero/
│   ├── keep/
│   │   ├── settings.json (api_keys without secrets refs, secrets in vault)
│   │   ├── knowledge/custom/
│   │   ├── agents/custom/
│   │   ├── solutions/
│   │   └── extensions/custom/
│   └── cache/ -> /tmp/council/agent-zero/ -> workdir/tmp, tmp, logs
├── shared/
│   ├── memory.md                # Cross-agent shared memory, all 3 R/W
│   └── skills/                  # Skills shared across all 3
├── journal/
│   ├── .git/                    # Git versioned council decisions
│   ├── 2026-08-04-abc123.md
│   └── ...
└── council/
    ├── council.yaml             # Council config: mode debate, strategy majority
    ├── storage-stats.json       # Storage usage per agent
    └── dashboard.db             # SQLite for dashboard (light)
```

### Bind Mount Magic for Isolation:

Each agent sees its own home but keep/cache split via symlinks + bind mounts set up by `council-persist-mount` + `council-storage-setup`:

```bash
# Hermes: HERMES_HOME=/var/lib/council/hermes/real_home
# real_home contains symlinks:
#   sessions -> /tmp/council/hermes/sessions (tmpfs)
#   logs -> /tmp/council/hermes/logs
#   image_cache -> /tmp/council/hermes/image_cache
#   SOUL.md -> keep/SOUL.md (real file on LUKS)
#   MEMORY.md -> keep/MEMORY.md
#   ...

# Same for OpenClaw and Agent Zero
```

This way agent code unchanged, but heavy writes go to RAM (no USB wear), important writes go to encrypted LUKS.

---

## 3. Dashboard - One to Rule All 3

### URL: https://council.local:8443 (self-signed, LAN offline like Reefy) or http://localhost:8443

**Backend:** FastAPI + WebSocket from council-core, already built in `council/orchestrator/main.py`

**Frontend Enhanced (new design):**

```
+-----------------------------------------------------------+
| 🗝️ CouncilKey-Os - Dashboard    [Storage: 230MB/120GB] [Encrypted: ✅] |
| Mode: debate | Strategy: majority | Uptime: 2h | Boot: 15s |
+-----------------------------------------------------------+
| [🧙 Hermes Sage] [🦞 OpenClaw Executor] [🔧 Agent0 Builder] | All Online
| Hermes: Memory 12MB, Skills 23 (5 new), Last skill: council-abc | [Shell] [Logs] [Restart] |
| OpenClaw: Memory 8MB, Skills 15, Gateway 18789 | [Shell] [Control UI] |
| Agent0: Knowledge 5MB, Solutions 12, Workdir tmp 200MB (will delete) |
+-----------------------------------------------------------+
| 💬 Ask Council (broadcast parallel) |
| [Input: Build me a website] [Ask] [Vote: majority] |
| Responses 3 + Voting visualization + Final synthesis |
+-----------------------------------------------------------+
| 🧠 Storage Optimizer (what makes sense) |
| Keep: 230MB (SOUL, MEMORY, USER, skills, cron, pairing, secrets) |
|   - Hermes: 45MB (SOUL 3KB, MEMORY 120KB, USER 80KB, skills 23 files 40MB, cron 3) |
|   - OpenClaw: 30MB (soul 2KB, skills 15 files 28MB) |
|   - Agent0: 20MB (knowledge custom 10MB, solutions 8MB) |
|   - Shared: 5MB (memory.md + journal 50 files) |
|   - Secrets: 1KB encrypted |
| Cache (RAM tmpfs, delete on unplug): 1.2GB |
|   - sessions: 800MB (will delete), logs: 300MB, image_cache: 100MB |
| [Optimize Now] [Schedule daily] [Show what will be deleted] |
+-----------------------------------------------------------+
| 📓 Journal - Git versioned council decisions |
| 2026-08-04 14:23 build-website - Consensus 3/3 - Best: agent-zero |
| 2026-08-04 14:10 explain-quantum - Consensus 2/3 - Best: hermes |
| [Search] [Export] |
+-----------------------------------------------------------+
| ⚙️ Control - Terminal + Secrets |
| [Terminal: hermes shell] [openclaw shell] [agent-zero shell] [council shell] |
| Secrets: ANTHROPIC_KEY ✅, OPENAI ✅, GEMINI ✅ [Edit GPG] |
| API: Nous Portal ✅ 300+ models |
| Network: WiFi council-wifi, Tailscale ✅, council.local |
+-----------------------------------------------------------+
```

**Features:**
- Agent status cards from `/api/status` with port check
- Ask council → `/api/council/ask` parallel broadcast → voting visualization
- Storage optimizer: Show keep vs cache breakdown, what will be deleted on unplug, button to optimize now
- Journal: Git log searchable via FTS5
- Shell: `podman exec -it hermes sh` or local exec via websocket (xterm.js)
- Secrets: GPG edit, podman secret create, Nous Portal OAuth

**Terminal access:** Each agent also works via normal terminal:
```bash
council shell hermes   # podman exec -it hermes zsh or local .venv
hermes                 # Hermes TUI direct
openclaw               # OpenClaw CLI
agent-zero             # Agent Zero run_ui.py
```

---

## 4. Cleanup on Unplug - How it works

### Why not delete while running?
We keep cache in tmpfs RAM (`/tmp/council/*`), so it's already not on USB. On unplug (power off), RAM cleared automatically. PLUS we have shutdown hook to clean any stray cache that accidentally landed on persistence (if tmpfs full fallback).

### Systemd Services:

**council-persist-mount.service:**
- Type=oneshot, Before council agents
- Finds persistence partition via label `casper-rw` or `COUNCIL_PERSIST` or `writable`
- If LUKS: `cryptsetup open` (plymouth ask passphrase or auto via USB dongle keyfile like Reefy)
- Mounts to `/var/lib/council`
- Creates keep/ and cache/ structure
- Sets up symlinks: sessions → /tmp/council/..., logs → /tmp/..., etc.
- Creates tmpfs mounts: `mount -t tmpfs -o size=2G,mode=0755 tmpfs /tmp/council`

**council-storage-setup.service:**
- After persist-mount, before agent services
- Initializes keep/ with defaults if first boot: SOUL.md default, config.yaml, council.yaml
- Migrates secrets from old locations to secrets/ vault
- Runs storage audit: calculates keep vs cache size, writes storage-stats.json

**council-cleanup.service:**
- `ExecStop=/usr/local/bin/council-cleanup`
- Runs on shutdown/reboot (when unplug, OS shutdown triggers)
- Deletes: /tmp/council/* (tmpfs will be cleared anyway but explicit), also cleans any cache that leaked to persistence: `rm -rf /var/lib/council/*/cache/* /var/lib/council/hermes/real_home/sessions/*` etc if they are real dirs not symlinks
- Syncs keep/ to ensure important data flushed: `sync`
- Journals: logs that cleanup happened, storage saved

**council-optimize.timer:**
- Daily timer, runs council optimizer: compresses MEMORY.md, dedupes skills via .usage.json, archives old journal to compressed, cleans workdir old files >7 days unless pinned

### Manual Optimize:

Dashboard button "Optimize Now" → calls `council storage optimize` which:

1. Scans keep/ for what is actually needed
2. For skills: reads .usage.json, if skill use_count=0 and last_activity >90 days and not pinned, moves to archive/
3. For MEMORY.md: runs LLM summarization to compress middle turns, protect head/tail (like Hermes context_compressor)
4. For journal: git gc, compress old .md to .md.gz after 30 days
5. For agent-zero workdir: keeps recent 7 days + solutions/ pinned, deletes rest
6. Calculates saved space

---

## 5. What Improvement Day by Day Means

**For User:** Each day you use CouncilKey:

- Hermes MEMORY.md grows with curated facts about you (from background_review)
- Hermes skills/ grows: agent creates new skill after you ask complex task (e.g., you ask to build website, it creates skill `build-minimal-website`)
- USER.md grows: better user modeling, knows your preferences (minimal design, security focus)
- OpenClaw soul.md refines? Actually manual but memory grows
- Agent Zero knowledge/custom/ grows + solutions/ grows
- Shared memory.md grows + journal git history grows

**So council becomes smarter, not just bigger raw logs.**

**Metrics dashboard should show:**
- Skills created per week
- Memory entries per week
- Cron jobs automated
- Journal decisions
- Storage keep growth (should be slow linear, not exponential like raw sessions)

If keep grows too fast (>500MB), optimizer suggests archiving old skills.

---

## 6. Implementation Steps

1. Build new storage layout scripts:
   - `builder/live/council-storage-setup.sh` (called inside chroot)
   - `usr/local/bin/council-persist-mount` (already exists but enhance with symlink logic)
   - `usr/local/bin/council-storage-optimizer` (Python)
   - `usr/local/bin/council-cleanup` (bash)

2. Update council orchestrator with storage API:
   - `/api/storage/stats` → keep vs cache size per agent
   - `/api/storage/optimize` → trigger optimize
   - `/api/storage/what-if` → show what would be deleted on unplug

3. Enhance dashboard frontend with storage optimizer UI

4. Update build scripts to use new layout

5. Create first-boot wizard that sets up encrypted persistence and secrets vault

---

## 7. Security for Pendrive

- LUKS2 encrypted persistence, passphrase + optional keyfile on separate tiny USB dongle (Reefy style)
- Secrets in secrets/ gpg encrypted with master.key that itself is LUKS protected
- No secrets baked into ISO (like Tank-OS podman secret pattern)
- Noatime + commit=60 for wear leveling
- RO squashfs for binaries = no wear, immutable, can't brick, A/B rollback via bootc

---

## Next: Implement
