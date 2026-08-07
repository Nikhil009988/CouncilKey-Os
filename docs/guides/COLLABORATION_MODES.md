# Collaboration Modes - Together + Alone + No Traces On Host After Unplug

**User Requirement:**
- Make it like they work together and if user wants they can work alone too
- After when user unplug pendrive the agents also remove from PC
- Data is stored in pendrive

---

## Modes

### 1. Together Mode (Council) - Default

All 3 agents work together as council, debate, vote, final synthesis.

**Flow:**
```
User: "Build me a website"
  ↓ Council Core broadcasts parallel to 3 agents (like Tank-OS Quadlets)
  ├── Hermes Sage (Memory & Learning): Provides context from MEMORY.md 1000 facts, skills/web-dev, USER.md preferences
  ├── OpenClaw Executor (Action & Comms): Plans file ops, search Firecrawl, shell/file/browser, notify Telegram after 2/3 vote
  └── Codex Builder (Code & Review): writes code in work_dir, edits files, runs terminal commands - locally, no Docker
  ↓ Collect 3 responses
  ↓ Vote: majority 2/3, or weighted, or llm_judge (Claude/GPT judges best), or hermes_decides Sage final
  ↓ If consensus (2/3 approve), execute approved actions
  ↓ Log to journal git versioned /var/lib/council/journal/*.md
  ↓ Final answer: synthesis of 3 perspectives + best agent + council decision
```

**Why together is better than single:**
- Safety: No single agent can act alone, 2/3 vote required prevents email deletion incident (real incident from Tank-OS docs)
- Memory: Hermes FTS5 historical context
- Action: OpenClaw phone bridge
- Transparency: Codex writes code inspectable
- Resilience: One offline, others vote, journal preserves

**CLI:**
```bash
council ask "Build website"  # together default majority
council ask --mode together --strategy majority "Build website"
council ask --mode together --strategy llm_judge "Build website"  # LLM Judge picks best
```

**Dashboard:** Council tab -> Ask Council -> Broadcast parallel -> Voting viz -> Final

### 2. Alone Mode (Solo) - Each Agent Works Alone

If user wants, each agent can work alone without council.

**Flow:**
```
User: "I want only Hermes to research quantum computing"
  ↓ Council Core checks --mode alone --agent hermes
  ↓ Only Hermes asked, no broadcast, no voting, direct response
  ↓ Log to journal but marked solo
```

**Use Cases:**
- User trusts one agent more for specific task
- Faster (no voting overhead)
- Testing individual agent
- Agent-specific features: Hermes TUI multiline editing, OpenClaw WhatsApp bridge, Codex local terminal/file/web tools

**CLI:**
```bash
council ask --mode alone --agent hermes "Research quantum computing"
council ask --mode alone --agent openclaw "Deploy website via shell"
council ask --mode alone --agent codex "Write code for website in work_dir"

# Direct solo terminals (like you know normally):
council shell hermes    # podman exec -it hermes sh or local .venv
hermes                  # Hermes TUI direct - Full TUI multiline editing, slash-command autocomplete, streaming tool output
openclaw                # OpenClaw CLI - openclaw onboard, openclaw gateway start 18789, openclaw dashboard 18788
codex                   # Codex CLI (interactive) - local execution

# Direct (single agent):
council hermes "prompt"      # Solo Hermes
council openclaw "prompt"    # Solo OpenClaw
council codex "prompt"  # Solo Codex
```

**Dashboard:** Agents tab -> Each card has [Solo Ask] button -> Ask only that agent

### 3. Hybrid (Together + Alone Mix) - Advanced

User can start together, then if consensus fails or user wants, switch to alone for refinement, then back to together for final vote.

**Example:**
```
User: "Build website" -> Together: 3 agents debate, no consensus (2/3 disagree)
User: "Ok, let Hermes alone design, then council vote"
  -> Alone: Hermes alone designs minimal website (uses MEMORY.md 1000 facts, skills/web-dev)
  -> Together: Council votes on Hermes design, OpenClaw executes, Codex writes code
```

---

## No Traces On Host After Unplug + Data Stored In Pendrive

**Requirement:** After unplug pendrive, agents also remove from PC, no traces, data stored in pendrive.

We have 2 profiles for this:

### Profile A: Portable USB (exFAT, No Reboot, Works on Any Windows/Linux Host) - Zero Traces via Env Redirect + Cleanup

**How the portable USB trick works:**

1. **All Binaries on Pendrive, Not Host:**
   - `bin/linux/node-v22.14-linux-x64/` - Portable Node.js runs directly from USB, no install
   - `tools/linux/openclaw/node_modules/` - OpenClaw npm global on USB
   - `tools/linux/hermes/.venv/` - Hermes Python venv on USB
   - `tools/codex/` - Codex CLI (npm) on USB
   - `tools/linux/council-core/.venv/` - Council core venv on USB
   - `bin/win/` - Same for Windows

2. **All Configs + Caches + Temp Redirected to Pendrive (Key Trick):**
   ```bash
   # In start.sh launcher
   export PATH="$USB/bin/linux/node-v22.14-linux-x64/bin:$PATH"
   export PATH="$USB/tools/linux/openclaw/node_modules/.bin:$PATH"
   export CLAUDE_CONFIG_DIR="$USB/config/.claude"
   export HERMES_HOME="$USB/config/council/hermes/real_home"  # real_home has keep/ -> persistence + cache/ -> /tmp/council (RAM) or USB/temp
   export OPENCLAW_HOME="$USB/config/council/openclaw/real_home"
   export CODEX_HOME="$USB/config/council/codex"
   export COUNCIL_HOME="$USB/config/council"
   export TMPDIR="$USB/temp"  # All temp to USB, not host /tmp
   export NPM_CONFIG_CACHE="$USB/temp/npm-cache"
   export NODE_COMPILE_CACHE="$USB/temp/node-cache"
   export XDG_CONFIG_HOME="$USB/config"
   export XDG_CACHE_HOME="$USB/temp/cache"
   export PYTHONUSERBASE="$USB/temp/python"
   mkdir -p "$USB/temp/npm-cache" "$USB/temp/node-cache" "$USB/temp/cache"
   ```

3. **Execution in Clean Shell (No Host Env Pollution):**
   ```bash
   cd "$HOME"  # Start in home but with portable env
   exec bash --norc --noprofile  # Clean shell without host .bashrc, .profile
   ```

4. **Cleanup on Exit (Unplug = Remove From PC):**
   ```bash
   # In start.sh, trap exit to cleanup
   cleanup() {
     echo "Cleaning up traces from host..."
     # Delete any leaked files in host /tmp that might have council in name
     rm -rf /tmp/council/* /tmp/*council* 2>/dev/null || true
     # Delete any leaked in host ~/.cache if we accidentally wrote there
     rm -rf ~/.cache/council* 2>/dev/null || true
     # Sync USB to ensure data stored in pendrive
     sync
     echo "All agents removed from PC, data stored in pendrive at $USB/config/council/"
   }
   trap cleanup EXIT
   ```

5. **Data Stored In Pendrive:**
   - `config/council/hermes/keep/` - SOUL.md, MEMORY.md, USER.md, config.yaml, skills custom, memories, cron, pairing, hooks - SMART kept
   - `config/council/openclaw/keep/` - soul.md, skills, pairing
   - `config/council/codex/keep/` - CODEX_HOME state (history, config)
   - `config/council/shared/memory.md` + `journal/*.md` git
   - `config/council/secrets/` - API keys GPG encrypted 700
   - `temp/` - Cache that would be deleted on unplug, but stored in pendrive temp/ for debugging, with option to delete via `council storage-optimize` or `council cleanup`

**Verification No Traces:**
```bash
# After unplug, on host PC check:
ls /tmp/ | grep council  # Should be empty after cleanup
ls ~/.config/ | grep council  # Should be empty (we redirected XDG_CONFIG_HOME to USB)
ps aux | grep council  # Should be no council processes after exit
# Data still in pendrive:
ls /media/$USER/COUNCIL/config/council/  # All keep/ data still there
```

**Result:** Plug USB -> Launch -> Code -> Exit -> Unplug, host untouched, no traces, data in pendrive.

### Profile B: Live Boot (True OS From Pendrive, No Host Touch At All) - Zero Traces by Design

**How Live Boot Works (from live-custom-ubuntu-from-scratch + Reefy + Tank-OS):**

1. **Boot From Pendrive, Not Host Disk:**
   - BIOS/UEFI boot menu picks USB
   - Kernel + initrd from `/casper/vmlinuz` + `/casper/initrd` on pendrive
   - Squashfs RO at `image/casper/filesystem.squashfs` on pendrive (Ubuntu base + council agents code + 5GB smart initial)
   - OverlayFS: Lower squashfs RO + Upper tmpfs RAM or persistence partition + Work
   - Host internal disk (e.g., /dev/sda Windows) NOT MOUNTED at all unless user explicitly mounts

2. **Persistence Optional:**
   - If persistence partition exists (label casper-rw or COUNCIL_PERSIST), mount to `/var/lib/council` for keep smart data
   - If no persistence or Amnesiac mode (kernel cmdline `toram` + `council.notrace`), everything in RAM, nothing written to pendrive either (true amnesiac like Tails)
   - For our design: Persistence LUKS2 encrypted ext4 for keep smart 100-300MB + 5GB RO smart initial

3. **Unplug = Remove From PC Completely:**
   - OS runs from pendrive + RAM, not host disk
   - When you shutdown and unplug pendrive, host PC reboots to its original OS (Windows/Linux) from internal disk
   - Host disk untouched, no council files, no agents, no traces
   - Data stored in pendrive persistence partition if you had persistence, still encrypted LUKS

**Verification No Traces:**
```bash
# After unplug and boot host original OS:
# Host should boot normal Windows/Linux, no council files
# If you had persistence, plug pendrive into another PC, boot, data still there:
ls /var/lib/council/  # All keep/ data still there
```

**Result:** Plug USB -> Boot CouncilKey OS -> Use 3 agents together or alone -> Shutdown -> Unplug -> Host untouched, original OS boots, data stored in pendrive persistence encrypted.

---

## Implementation in CouncilKey-Os

### CLI Now Supports Both Together + Alone

```bash
# Together (default) - Council debate + vote
council ask "Build website"  # together majority
council ask --mode together --strategy majority "Build website"
council ask --mode together --strategy llm_judge "Build website"

# Alone - Solo agent
council ask --mode alone --agent hermes "Research quantum computing"
council ask --mode alone --agent openclaw "Deploy website"
council ask --mode alone --agent codex "Write code in work_dir"

# Direct solo (like you know normally terminal too)
council hermes "prompt"  # solo
council openclaw "prompt"
council codex "prompt"
council shell hermes  # podman exec -it hermes sh
hermes  # Hermes TUI direct
openclaw  # OpenClaw CLI
codex  # Codex CLI

# Storage + no traces
council storage-audit  # Keep smart vs Cache RAM auto delete on unplug
council storage-what-if  # What would be deleted on unplug
council cleanup  # Manual trigger delete heavy on unplug logic
```

### Dashboard Now Supports Both

- **Council tab:** Together mode - Ask Council broadcast parallel 3 agents voting
- **Agents tab:** Each card has [Together] [Solo Ask] [Shell] buttons
  - Together: Adds that agent's perspective to council vote
  - Solo Ask: Ask only that agent alone
  - Shell: Open terminal for that agent alone

### Portable No-Traces Implementation

**`scripts/build-portable.sh` already does:**
- Downloads Node.js Linux+Win, resolves symlinks cp -rL for exFAT (no symlinks)
- Installs hermes (pip), openclaw + codex (npm) on USB
- Creates start.sh with env redirect to USB + trap cleanup EXIT

**Enhanced for together+alone + no traces:**

- start.sh now has:
  - Together + alone functions
  - Cleanup trap that deletes /tmp/council/* host traces + syncs USB
  - Data stored in USB/config/council/ keep/

- New script `scripts/verify-no-traces.sh` that checks host for traces after unplug

### Live Boot No-Traces Implementation

**`scripts/build-live-iso.sh` already does:**
- debootstrap noble -> chroot installs council agents to /opt/council/
- Sets up systemd services for 3 agents + council-core + persistence + storage-setup + cleanup
- mksquashfs RO + kernel+initrd + grub BIOS+UEFI + xorriso ISO

**Enhanced:**
- grub.cfg has 3 entries: Try Council Live (together), Try with Persistence (data stored in pendrive), Amnesiac No Trace (RAM only, no persist, true no traces even on pendrive)
- council-persist-mount.service finds persistence via blkid label casper-rw/COUNCIL_PERSIST, cryptsetup open LUKS, mounts to /var/lib/council
- Host disk not mounted by default, so no traces on host

---

## Summary for User Simple

**Together:** `council ask "Build website"` -> 3 agents debate + vote 2/3 approve -> final synthesis + journal git

**Alone:** `council ask --mode alone --agent hermes "Research quantum"` -> Only Hermes alone, no vote, faster

**You can switch:** Together for safety, alone for speed or agent-specific features (Hermes TUI, OpenClaw WhatsApp, Codex terminal)

**No Traces After Unplug:**

- **Portable:** All binaries, configs, caches, temp on pendrive USB, env vars redirected to USB, clean shell --norc --noprofile, trap cleanup EXIT deletes host /tmp/council/*, sync ensures data stored in pendrive config/council/ keep/. After exit + unplug, ps aux | grep council empty, ls /tmp/ | grep council empty, host untouched.

- **Live Boot:** OS boots from pendrive, runs in RAM + pendrive, host internal disk not mounted, not touched. Shutdown + unplug, host reboots original OS, no council files, no traces. Data stored in pendrive persistence LUKS encrypted if you had persistence.

**Data Stored in Pendrive:** Always in pendrive, not host:

- Portable: `USB/config/council/hermes/keep/` SOUL.md MEMORY.md USER.md skills/ etc. + `openclaw/keep/` + `codex/keep/` + `shared/memory.md` + `journal/*.md` git + `secrets/` GPG encrypted
- Live: `/var/lib/council/` same structure on persistence partition LUKS2 encrypted ext4, RO 5GB smart initial + RW 100-300MB daily learning

Both profiles ensure after unplug, agents removed from PC, data in pendrive.

---

## Next Implementation

- Update council/orchestrator/main.py to support --mode together|alone --agent hermes|openclaw|codex
- Update dashboard 6 tabs to have Together/Solo buttons
- Enhance start.sh with cleanup trap + verify-no-traces
- Update build-live-iso.sh grub.cfg with Amnesiac No Trace entry
- Create verify-no-traces.sh script
- Test portable no traces: run portable, exit, check host /tmp for traces
