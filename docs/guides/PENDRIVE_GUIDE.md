# CouncilKey-Os Pendrive Guide - 3 Agents Live, One Dashboard, Smart Storage

## Goal

Run the three agents (Hermes, OpenClaw, Codex) from a USB pendrive, control them from one dashboard (or the terminal), and keep only what makes them smarter — while deleting heavy session data automatically when the pendrive is unplugged.

This guide explains how the storage design achieves that.

---

## Storage research summary

We looked at how Hermes, OpenClaw and Codex each store data. Every agent has two kinds of data:

**Key finding:** Each agent has TWO types of data:

1. **Distilled Knowledge (LIGHT, 100-300MB after 1 year, MUST KEEP)** - This is what makes agents smarter daily:
   - `SOUL.md` / `soul.md` - Personality
   - `MEMORY.md`, `USER.md` - Curated long-term memory (not raw logs) - Hermes background_review process distills sessions -> MEMORY.md
   - `skills/*.md` custom + curator-managed + `.usage.json` (use_count, pinned) - **SELF-IMPROVEMENT** - Hermes creates new skill after complex task
   - `codex/` - Codex CLI state (history, config) - CODEX_HOME on the stick
   - `cron/`, `pairing/` - Automations + allowed Telegram/Discord users
   - `config.yaml`, `settings.json`, `openclaw.json` - Model choices, toolsets
   - `secrets/` - `.env`, `auth.json` (Nous Portal 300+ models), `api_keys` - MUST be LUKS encrypted
   - `shared/memory.md`, `journal/*.md` git - Cross-agent learnings

2. **Raw Heavy (HEAVY, 1-10GB per use, DELETE ON UNPLUG)** - Regeneratable, not needed to learn:
   - `sessions/` Hermes `session_{sid}.json` + `sessions.json` 90 days + FTS5 SQLite - **BIGGEST 800MB-10GB**
   - OpenClaw `data/` raw conversation history
   - `logs/` all agents
   - `image_cache/`, `audio_cache/`, `cache/`, `tmp/`, `__pycache__/`
   - `lsp/bin/` 100MB+ LSP binaries
   - Codex session files older than 7 days
   - `.venv/` 500MB+ each - Should be in RO squashfs ISO, not persistence wear

**Why delete raw is safe:** Hermes `learning_graph.py` + `background_review.py` shows after N turns (skill_nudge_interval=10), auxiliary LLM reviews conversation, extracts skills into `skills/*.md` and facts into `MEMORY.md`. So raw sessions are already distilled.

---

## Pendrive Partition Design

### Partition Layout (like Reefy + Tank-OS):

```
/dev/sdX1: EFI 512MB FAT32 LABEL=COUNCIL_EFI (grub, shim, bootx64.efi)
/dev/sdX2: LIVE 8GB squashfs LABEL=COUNCIL_LIVE (RO immutable, contains node+python+agents code, no wear, A/B rollback)
/dev/sdX3: PERSIST rest LUKS2 encrypted ext4 LABEL=COUNCIL_PERSIST (RW, noatime,commit=60, holds only KEEP smart data 100-300MB)
```

### Inside LUKS at `/var/lib/council/` (decrypted):

```
/var/lib/council/
├── secrets/ (700, gpg encrypted, LUKS protected)
│   ├── hermes.env.gpg, openclaw.env.gpg, agentzero.settings.gpg
├── hermes/
│   ├── keep/ (real files on LUKS - SMART)
│   │   ├── SOUL.md, MEMORY.md, USER.md, config.yaml, skills/custom + .usage.json, memories/, cron/, pairing/, hooks/
│   └── real_home/ (what HERMES_HOME points to, symlinks)
│       ├── SOUL.md -> keep/SOUL.md
│       ├── sessions -> /tmp/council/hermes/sessions (tmpfs RAM - auto delete)
│       ├── logs -> /tmp/council/hermes/logs
│       └── image_cache -> /tmp/council/hermes/image_cache
├── openclaw/
│   ├── keep/ soul.md, MEMORY.md, skills custom, pairing/
│   └── real_home/ soul.md->keep/, skills->keep/, logs->/tmp/council/openclaw/logs
├── codex/
│   ├── keep/ settings.json, knowledge/custom/, solutions/, agents/custom/
│   └── CODEX_HOME (history, config) on the stick
├── shared/memory.md (cross-agent R/W) + skills/
├── journal/.git/ (git versioned decisions)
└── council/council.yaml
```

**Magic:** Agent code unchanged, but heavy writes go to RAM tmpfs (no USB wear, auto delete on unplug), smart writes go to encrypted LUKS.

**Tmpfs:** `/tmp/council/*` 2GB tmpfs RAM - on power off (unplug), RAM cleared automatically. Plus `council-cleanup.service` ExecStop on shutdown deletes any leaked cache + syncs keep/.

---

## Dashboard - One to Control All 3 + Terminal

URL: `https://council.local:8443` or `http://localhost:8443`

We built `council/dashboard/new_dashboard.py` v2 with:

**Tabs:**

1. **Council:** Ask council - broadcast parallel to 3 agents (Tank-OS Quadlet style), voting visualization (majority/weighted/llm_judge/hermes_decides), final synthesis

2. **Agents:** 3 cards Hermes Sage, OpenClaw Executor, Agent0 Builder - status online/offline, keep vs cache size, [Shell] [Logs] [Restart] [Open Port] buttons

3. **Storage Optimizer:** 
   - Audit Now -> shows keep smart 100-300MB vs cache RAM 1-10GB auto delete, storage bar visual
   - What If Delete? -> lists files that would be deleted on unplug with reason
   - Optimize Now -> archives unused skills >90d not pinned, cleans workdir old >7d, compresses journal >30d to .gz, calculates saved space
   - Setup Persist Structure -> first boot creates optimized layout

4. **Journal:** Git versioned council decisions, searchable, export

5. **Terminal:** xterm.js via WebSocket, `council shell hermes` = `podman exec -it hermes sh`, also `hermes` TUI, `openclaw` CLI, `codex` CLI

6. **Secrets:** Vault - shows ANTHROPIC_KEY ✅, OPENAI ✅, GEMINI ✅, Nous Portal single sub 300+ models, Edit GPG + podman secret create pattern like Tank-OS

**Terminal access also works normally:**

```bash
council status
council ask "build website"
council shell hermes
hermes                 # Hermes TUI direct
openclaw gateway start # 18789
openclaw dashboard     # Control UI 18788
codex                  # Codex CLI (local, no Docker)
```

---

## How It Learns Day By Day (What Improvement Means)

**Each day you use pendrive:**

- Hermes MEMORY.md grows with curated facts (from background_review)
- Hermes skills/ grows: you ask complex task → agent creates new skill `build-minimal-website` + updates .usage.json use_count
- USER.md grows: better user modeling, knows you prefer minimal, secure
- OpenClaw soul.md + memory grows
- Codex state grows on the stick (council-data/codex)
- Shared memory.md + journal git grows

**Metrics dashboard shows:** Skills created per week, Memory entries per week, Cron jobs, Journal decisions. Storage keep growth should be slow linear, not exponential like raw sessions. If keep >500MB, optimizer suggests archiving old skills.

---

## How to Build Pendrive Now (Step by Step)

### Option 1: Portable (5 min, no BIOS, works on any Windows/Linux host)

Best for quick test, no reboot.

```bash
git clone https://github.com/Nikhil009988/CouncilKey-Os
cd CouncilKey-Os
# Format USB exFAT
sudo mkfs.exfat -n COUNCIL /dev/sdX1  # replace sdX1 with your USB partition
sudo mount /dev/sdX1 /mnt/council

# Build portable council - optimized storage version
./scripts/build-portable.sh /mnt/council
# If nodejs.org fails in sandbox, manually download node-v22.14-linux-x64.tar.xz to bin/linux/
# Our new storage optimizer version uses council/storage/optimizer.py for keep/cache split

# Edit secrets (encrypted later)
nano /mnt/council/config/council/env.sh
# ANTHROPIC_API_KEY=...
# Or use Nous Portal: hermes setup --portal (single sub 300+ models)

# Safely eject
sudo umount /mnt/council

# On any PC when you need agents:
# Linux:
bash /media/$USER/COUNCIL/start.sh
council status
council storage-audit   # shows keep 230MB smart vs cache 1.2GB delete on unplug
council ask "hello council, why 3 better than 1?"
council dashboard --port 8443  # opens https://localhost:8443 with 6 tabs

# Windows: double-click start.bat
```

**Portable start.sh does:**
- Finds portable Node.js, Python venvs (resolves symlinks cp -rL for exFAT)
- Sets HERMES_HOME=/USB/config/council/hermes/real_home (symlinked keep/cache)
- Redirects TMPDIR, NPM_CONFIG_CACHE, XDG_CACHE to USB/temp + /tmp/council tmpfs
- Starts council-core dashboard background
- Gives clean bash with council, hermes, openclaw, codex in PATH
- No traces on host

### Option 2: Live ISO (30-60 min, true bootable pendrive, recommended)

Based on `mvallim/live-custom-ubuntu-from-scratch` + our optimized storage setup.

**Build Host:** Ubuntu 22.04+/24.04+ with 50GB free.

```bash
sudo apt install debootstrap squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin mtools dosfstools

git clone https://github.com/Nikhil009988/CouncilKey-Os
cd CouncilKey-Os

sudo ./scripts/build-live-iso.sh noble amd64
# What it does:
# 1. debootstrap noble minimal to chroot/
# 2. Mount dev/run/proc/sys
# 3. Chroot: apt install linux-generic casper network-manager docker.io podman python3 nodejs 22 + council agents to /opt/council/
# 4. Setup optimized storage: builder/live/council-storage-setup.sh creates keep/cache split + tmpfs symlinks
# 5. Systemd units: council-persist-mount.service (finds LUKS, mounts), council-storage-setup.service, council-hermes.service (1001), council-openclaw.service (1002), council-agentzero.service (1003), council-core.service, council-cleanup.service ExecStop
# 6. mksquashfs chroot/ image/casper/filesystem.squashfs -comp xz (RO, no wear)
# 7. Kernel+initrd, grub.cfg (Try Council Live, Try Persistence, Amnesiac No Trace, Install), EFI FAT efiboot.img, BIOS bios.img, manifest, md5sum, xorriso ISO

# Output: output/councilkey-os-1.0-noble-amd64-live.iso (4-8GB)

# Flash to USB
lsblk  # find your USB, e.g., /dev/sdb NOT /dev/sda
sudo dd if=output/councilkey-os-1.0-noble-amd64-live.iso of=/dev/sdX bs=4M status=progress && sync

# Create persistence partition (rest of disk)
sudo parted /dev/sdX -- mkpart primary ext4 8GiB 100%
# For encrypted (recommended):
sudo cryptsetup luksFormat /dev/sdX3
sudo cryptsetup open /dev/sdX3 council-persist
sudo mkfs.ext4 -L casper-rw /dev/mapper/council-persist
# Or unencrypted:
sudo mkfs.ext4 -L casper-rw /dev/sdX3

# Boot: plug USB, hit Esc/F12/Del boot menu, pick USB, login council/council
# First boot wizard: asks WiFi, API keys (stored as LUKS+gpg secrets), persistence passphrase
# Then:
council status
council storage-audit
council dashboard  # https://council.local:8443 from any device on LAN (Reefy style offline LAN access)
```

### Option 3: Bootc Immutable (2 hr, most secure, like Tank-OS + Reefy, cannot brick)

**Build Host:** Fedora 44+ or Ubuntu with podman.

```bash
sudo dnf install podman make git qemu-kvm

git clone https://github.com/Nikhil009988/CouncilKey-Os
cd CouncilKey-Os

cp builder/bootc/config.toml.example builder/bootc/config.toml
# Edit config.toml: add your ssh pub key for VM test: cat ~/.ssh/id_ed25519.pub

./scripts/build-bootc.sh qcow2
# 1. Builds council-core container localhost/councilkey-council-core
# 2. Builds bootc image localhost/councilkey-os:latest FROM fedora-bootc:44 + podman, 4 users with subuid, rootfs-overlay with Quadlets
# 3. bootc-image-builder: podman run privileged quay.io/centos-bootc/bootc-image-builder -> qcow2/raw/iso
# Output: output/bootc/qcow2/disk.qcow2, output/bootc/raw/disk.raw

# Test QEMU
qemu-system-x86_64 -M virt -accel kvm -cpu host -smp 4 -m 4096 -drive file=output/bootc/qcow2/disk.qcow2,format=qcow2,if=virtio -device virtio-net-pci,netdev=net0 -netdev user,id=net0,hostfwd=tcp::2222-:22 -nographic
# Other terminal:
ssh -p 2222 council@localhost
podman ps  # should show 3 containers: hermes, openclaw, council-core (codex runs locally, no container)
council status
journalctl -u council-core -f

# Flash RAW to USB (like Reefy)
sudo dd if=output/bootc/raw/disk.raw of=/dev/sdX bs=4M status=progress && sync
# Or Balena Etcher GUI cross-platform

# Boot physical: disable Secure Boot in BIOS, pick USB
# Upgrade: sudo bootc switch --apply quay.io/your-org/councilkey-os:latest (atomic, rollback on fail)
```

---

## First Boot Wizard (on pendrive)

```
Welcome to CouncilKey-Os

1. WiFi setup: scan + connect (like Reefy 15s boot optimized)
2. API Keys: Anthropic, OpenAI, Gemini, OpenRouter OR Nous Portal single (hermes setup --portal covers 300+ models + tool gateway search/image/TTS/browser)
   Input hidden, stored as podman secret + gpg encrypted in /var/lib/council/secrets/ 700, master key LUKS protected
3. Create council admin password (for LUKS + dashboard)
4. Choose persistence: [Encrypted LUKS + keyfile on separate tiny USB dongle like Reefy] [Unencrypted] [Amnesiac No Trace mode tmpfs]
5. Test: council ask "hello council" -> 3 agents debate + vote + journal git commit
```

---

## CLI After Boot (terminal too)

```bash
council status              # 3 agents + storage keep vs cache
council ask "prompt"        # broadcast parallel, vote majority, journal log
council ask --strategy llm_judge "prompt"
council storage-audit       # keep smart 230MB vs cache RAM 1.2GB
council storage-what-if     # show what would be deleted on unplug
council storage-optimize    # archive unused skills >90d, clean workdir >7d, compress journal >30d
council storage-setup       # setup keep/cache split + tmpfs symlinks (first boot)
council logs --agent hermes -f
council shell hermes        # podman exec -it hermes sh
council shell openclaw
council shell codex
hermes                      # Hermes TUI direct
openclaw onboard            # Setup OpenClaw
openclaw gateway start      # 18789
openclaw dashboard          # Control UI 18788
codex                       # Codex CLI (local)
council dashboard --port 8443  # Unified dashboard https://localhost:8443 with 6 tabs
council journal             # git log of council decisions
council cleanup             # manual trigger delete heavy on unplug logic + sync keep
```

---

## Security (from Tank-OS + Reefy scan)

- No docker daemon, rootless Podman only, user namespaces hermes 1001->101001 via subuid 100000-165535
- RO root squashfs immutable, can't brick, atomic rollback via bootc
- Secrets not baked into image, runtime injection podman secret + gpg encrypted secrets/ 700, LUKS2 encrypted persistence
- policyd gates every tool call, sensitive needs 2/3 vote (prevents OpenClaw email deletion incident from Tank-OS docs)
- SBOM CycloneDX + cosign signing (like CX Linux)
- Works offline (Ollama qwen2.5:7b local), LAN dashboard when no internet (Reefy)

---

## Roadmap Done

- [x] Deep audit of the 3 agents' storage (keep vs cache split)
- [x] Optimized partition design
- [x] Storage optimizer (council/storage/optimizer.py) audit/what-if/optimize/setup
- [x] Cleanup on unplug (council/storage/cleanup.sh + council-cleanup.service)
- [x] Optimized storage setup (builder/live/council-storage-setup.sh)
- [x] Unified dashboard v2 (council/dashboard/new_dashboard.py) 6 tabs Council/Agents/Storage/Journal/Terminal/Secrets
- [x] Council orchestrator v2 (main.py) with storage APIs + terminal
- [x] 3 build profiles updated to use optimized layout
- [x] Portable demo working: keep 6KB smart vs cache 5MB delete on unplug tested

---

## Try Now in This Repo (no USB needed)

```bash
python3 council/orchestrator/main.py storage-setup   # create keep/cache split
python3 council/orchestrator/main.py storage-audit    # audit
python3 council/orchestrator/main.py storage-what-if # what would delete
python3 council/orchestrator/main.py status           # 3 agents + storage
python3 council/orchestrator/main.py ask "why 3 agents better than 1 for pendrive OS?"
python3 council/dashboard/new_dashboard.py            # dashboard v2 at http://localhost:8000 with storage optimizer UI
# Or:
python3 council/orchestrator/main.py dashboard --port 8443 --host 0.0.0.0
```

---

## Next For You

1. Pick profile: portable for quick test, live ISO for true bootable, bootc for most secure
2. Real USB 64GB+ USB3 (3x faster than USB2 even in USB2 port from forum scan)
3. Add Ollama to live ISO for 100% offline: `ollama pull qwen2.5:7b` (like ClawOS)
4. Nous Portal for single API covering 300+ models
5. Test storage optimizer daily, watch keep growth slow linear, cache auto delete
6. Build in public early, ISO final stage (ClawOS approach)

All code in branch main, ready to push.
