# Deep Storage Audit - What 3 Agents Actually Store & What Matters for Pendrive

Date: 2026-08-04 - Full source scan of hermes-agent, openclaw, agent-zero

---

## Hermes Agent (NousResearch) - ~/.hermes

### From hermes_constants.py + hermes_cli/config.py scan

**Core paths via get_hermes_home() / get_hermes_dir():**
- Default: `~/.hermes` or `$HERMES_HOME`

**Full file tree from code (config.py line 906-907):**

["cron", "sessions", "logs", "logs/curator", "memories",
 "pairing", "hooks", "image_cache", "audio_cache", "skills"]
Plus files: config.yaml, .env, SOUL.md, MEMORY.md, USER.md, auth.json, sessions.json, .usage.json

**What each file really does (importance for pendrive):**

| Path | Size | Grows? | Needed smarter? | Keep? | Why |
|------|------|--------|------------------|-------|-----|
| SOUL.md | 2-5KB | No | YES | ✅ KEEP | Core identity |
| MEMORY.md | 5KB-200KB | Yes slowly | YES | ✅ KEEP | Curated long-term memory |
| USER.md | 5KB-100KB | Yes slowly | YES | ✅ KEEP | User modeling |
| config.yaml | 5-15KB | Slowly | YES | ✅ KEEP | Model choices, toolsets |
| .env | 1KB | No | YES | ✅ KEEP ENCRYPTED | API keys |
| auth.json | 2KB | No | YES | ✅ KEEP ENCRYPTED | Nous Portal OAuth 300+ models |
| skills/* | 10KB-5MB each | Yes - agent creates new skills | YES | ✅ KEEP selective | MOST IMPORTANT - self-improvement |
| skills/.usage.json | KB | Yes | YES | ✅ KEEP | use_count, pinned, last_activity |
| memories/ | ? | Slowly | YES | ✅ KEEP | |
| cron/ | KB per job | Slowly | YES | ✅ KEEP | Automations |
| pairing/ | KB | Slowly | YES | ✅ KEEP | Allowed users |
| hooks/ | KB | Slowly | YES | ✅ KEEP | Custom logic |
| sessions/ | 10MB-1GB | FAST | NO | ❌ DELETE on unplug | BIGGEST HEAVY - session_{sid}.json snapshots, 90 days retention, FTS5. But background_review curates into MEMORY.md+skills so safe |
| sessions.json | MB | Fast | NO | ❌ DELETE | Legacy mirror |
| logs/ | 5MB-500MB | Fast | NO | ❌ DELETE | Debug only |
| image_cache/, audio_cache/ | 10MB-500MB | Fast | NO | ❌ DELETE | TTS, image gen cache |
| lsp/bin | 100MB+ | Once | NO | ❌ DELETE | Can re-download |

**Learning mechanism:** After N turns (skill_nudge_interval=10), background_review LLM reviews conversation, extracts skills into skills/*.md. So sessions RAW, MEMORY.md+skills DISTILLED.

**What makes Hermes smarter:** MEMORY.md+USER.md growth, skills/*.md creation, skills/.usage.json, cron/, SOUL.md refinement. Keep ~50MB after 1 year vs sessions+logs+cache 2-10GB.

---

## OpenClaw - ~/.openclaw

Structure: soul.md, .env, openclaw.json, skills/, data/memory.db (LanceDB), extensions/, logs/, cache/, gateway.token, pairing/

| Path | Keep? |
|------|-------|
| soul.md | ✅ KEEP |
| .env / openclaw.json | ✅ KEEP ENCRYPTED |
| skills/ user-created | ✅ KEEP |
| data/ memory.db distilled | ✅ KEEP distilled, ❌ DELETE raw history |
| extensions/ custom | ✅ KEEP custom |
| pairing/ | ✅ KEEP |
| cron/jobs | ✅ KEEP |
| sessions, logs, cache | ❌ DELETE |

Size: Keep ~100MB, delete 1-5GB.

---

## Agent Zero - work_dir / knowledge / usr

```
usr/settings.json - API keys, profile, secrets
knowledge/custom/ - User custom knowledge IMPORTANT
agents/ - prompts/*.md custom behavior
extensions/ - Plugin Hub 100+ plugins
solutions/ - Previous solutions memorized
workdir/ - Code artifacts, HEAVY but may have valuable
tmp/, logs - temp
```

| Path | Keep? |
|------|-------|
| usr/settings.json | ✅ KEEP ENCRYPTED |
| knowledge/custom/ | ✅ KEEP |
| agents/*/prompts custom | ✅ KEEP custom |
| extensions/ custom | ✅ KEEP custom |
| plugins/ | ✅ KEEP list |
| solutions/ | ✅ KEEP |
| workdir/ | ⚠️ PARTIAL - Keep recent+pinned, delete old temp |
| tmp/, logs, __pycache__ | ❌ DELETE |

**Learning:** Custom prompts in agents/ + Knowledge/custom + Solutions/ + settings.json variables.

---

## Summary - What must keep to improve daily

1. Identity: SOUL.md, soul.md, USER.md, agent profile
2. Long-term Memory Distilled: MEMORY.md, USER.md, knowledge/custom/, data/memory.db distilled
3. Procedural Memory: skills/*.md user-created, .usage.json, extensions custom, solutions/
4. User & People: pairing/, allowed users
5. Automation: cron/
6. Secrets: .env, auth.json, api_keys - LUKS encrypted
7. Config: config.yaml, openclaw.json, settings.json
8. Journal: Council shared memory + journal git

**Heavy junk to delete:**
1. Sessions: session_{sid}.json, sessions.json, conversation history
2. Logs
3. Caches: image_cache, audio_cache, cache/, tmp, __pycache__
4. Transient Workdir
5. Binaries: lsp/bin, .venv (keep as RO squashfs)

**Target:** Keep 100-300MB after 1 year, delete 1-10GB per unplug.

---

