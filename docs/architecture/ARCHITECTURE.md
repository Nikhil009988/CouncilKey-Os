# CouncilKey-Os - Architecture: Live Council of 3 Agents on One Pendrive

## Vision
> A bootable pen drive that turns ANY PC into a secure council of AI agents: Hermes, OpenClaw, and Codex - working together, debating, voting, never leaving traces on host.

Plug in → Boot → Council is alive → Unplug → Host untouched.

---

## High Level Concept

```
┌─────────────────────────────────────────────────────────────┐
│                    Pendrive (64GB+ recommended)             │
│                                                             │
│  Partition 1: EFI (FAT32, 512MB) - bootloaders (grub, shim) │
│  Partition 2: Live System (ISO9660 / squashfs 4-8GB)       │
│               - Read-only root, immutable, A/B              │
│  Partition 3: Persistence (LUKS2 encrypted ext4, rest)     │
│               - /var/lib/council/                           │
│               - Agent memories, skills, conversations        │
│               - API keys (encrypted at rest)                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            |
                            | BIOS/UEFI Boot
                            v
┌─────────────────────────────────────────────────────────────┐
│                     Live Linux Kernel (6.18 LTS)            │
│  - Optimized 15s boot (systemd-analyze critical-chain)      │
│  - Drivers: Nvidia open, WiFi RTL, Intel, AMD GPU           │
│  - Mounts: overlayfs (RO squashfs + RW persistence)         │
│                                                             │
│  systemd services:                                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ council-persistence.service (LUKS unlock, mount)    │    │
│  │ council-network.service (WiFi + Tailscale VPN)      │    │
│  │ council-hermes.service (rootless podman, UID 1000)  │    │
│  │ council-openclaw.service (rootless podman, UID 1001)│    │
│  │ codex: local CLI (no container)                  │   │
│  │ council-core.service (orchestrator + dashboard)     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Council Core (Python + FastAPI + WebSocket):               │
│  - Receives user prompt via Web UI / CLI / Telegram         │
│  - Broadcasts to 3 agents in parallel (delegate pattern)    │
│  - Collects 3 responses                                     │
│  - Runs voting logic: consensus, majority, judge LLM        │
│  - Logs to council journal (git-versioned markdown)          │
│  - Dashboard at https://council.local:8443                  │
└─────────────────────────────────────────────────────────────┘
```

---

## The Three Agents - Roles in Council

### Hermes (Agent of Memory & Learning)
- **Role:** The Sage - remembers everything, learns, creates skills
- **Strengths from code scan:** Self-improving skills, FTS5 memory search, 15+ messaging platforms, trajectory training, 40+ tools
- **In Council:** Provides historical context, long-term memory, learns from council decisions to create new skills
- **Port:** 18790 (gateway), 8765 (internal RPC)
- **Storage:** /var/lib/council/hermes/ (MEMORY.md, skills/, sessions SQLite)
- **Backend:** Python 3.11 + uv venv, runs local or Docker

### OpenClaw (Agent of Action & Communication)
- **Role:** The Executor - does things, controls host, talks everywhere
- **Strengths:** 310k stars, WhatsApp/Telegram/Discord/Signal bridge, shell/file access, 100+ skills, 24/7 gateway, soul.md personality
- **In Council:** Executes final approved actions, bridges to user's phone, handles 50+ integrations
- **Port:** 18789 (gateway), 18788 (control UI)
- **Storage:** /var/lib/council/openclaw/.openclaw/
- **Backend:** Node.js 24, rootless Podman container `ghcr.io/openclaw/openclaw:latest` + openshell

### Codex (Agent of Code & Review)
- **Role:** The Builder - writes code, edits files, runs terminal commands, transparent
- **Strengths:** Local execution (no Docker), terminal + file editing + web tools built in, works with OpenAI/OpenRouter keys
- **In Council:** When the council needs code, tool creation or file manipulation, it delegates to Codex
- **Port:** none (interactive CLI; gateway bridge via `COUNCIL_CODEX_URL` if you expose one)
- **Storage:** /var/lib/council/codex/ (CODEX_HOME; on the pendrive: council-data/codex)
- **Backend:** Codex CLI - npm `@openai/codex`, runs locally

---

## Council Orchestration - How They Talk

### Voting Patterns (configurable in /etc/council/council.yaml)

```yaml
council:
  mode: "debate"  # debate, vote, hierarchical, unanimous
  agents:
    hermes:
      weight: 1
      role: "memory"
      timeout: 60s
    openclaw:
      weight: 1
      role: "action"
      timeout: 60s
    codex:
      weight: 1
      role: "builder"
      timeout: 120s
  consensus:
    strategy: "majority"  # majority, weighted, llm_judge, hermes_decides
    llm_judge: "claude-sonnet" # if strategy=llm_judge, which model judges
    min_agreement: 2  # 2 out of 3 must agree
  communication:
    shared_memory: "/var/lib/council/shared/memory.md" # all agents can read/write
    message_bus: "mqtt" # mqtt or redis, lightweight pub/sub
```

### Flow for User Prompt: "Build me a website"

```
User -> Council Core (HTTP POST /api/council/ask)
  |
  |-parallel-->
  |           -> Hermes: "I remember you liked minimal design, I'll provide context"
  |           -> OpenClaw: "I'll manage files and deployment"
  |           -> Codex: "I'll write the HTML/CSS/JS code"
  |
  |<-- responses --
  Council Core aggregates:
    Hermes: context + risks + skill suggestions
    OpenClaw: file ops plan + deployment steps
    Codex: actual code artifacts
  |
  |-> Voting: If 2/3 agree code is safe, proceed
  |-> LLM Judge (optional): Claude judges if code meets requirements
  |
  Council -> User: Final answer with code + context + execution plan
  Council -> Journal: git commit to /var/lib/council/journal/ with decision log
```

### Safety - No Single Agent Can Act Alone
Inspired by Tank-OS and Hermes approval gates:
- Each agent's tool calls are intercepted by policyd (from ClawOS)
- Sensitive actions require 2/3 approval
- Root filesystem read-only, agents can only write to /var/lib/council/
- API keys via podman secret, not env files

---

## Three Build Profiles

### Profile 1: Portable USB (Fastest, exFAT, No BIOS change needed)

```
USB (exFAT)
  /bin/linux/node-v22.14-linux-x64/  (portable Node)
  /bin/linux/python-3.11/            (portable Python + uv)
  /tools/linux/openclaw/             (npm global)
  /tools/linux/hermes/               (venv)
  /tools/codex/                     (npm @openai/codex)
  /tools/linux/council-core/         (orchestrator)
  /config/                           (all configs)
  /temp/                             (all caches)
  /start.sh                          (launcher)
```

- `setup.sh` similar to portable-agent-usb but extended
- Handles symlink resolution via `cp -rL`
- Uses `TMPDIR=$USB/temp` trick
- Launch: `bash /media/$USER/COUNCIL/start.sh` -> starts 3 agents + council dashboard on random ports
- No boot, works on any Windows/Linux host without install

**Pros:** 5 min setup, works everywhere, no BIOS.
**Cons:** Not isolated, uses host OS.

### Profile 2: Live ISO - Ubuntu from Scratch (Recommended for pendrive boot)

Based on `live-custom-ubuntu-from-scratch` path:

**Build steps:**
1. Host needs: debootstrap, squashfs-tools, xorriso, grub-pc-bin, grub-efi-amd64-bin
2. `scripts/build-live-iso.sh noble` -> 
   - debootstrap Ubuntu Noble 24.04 minimal to chroot/
   - chroot: install kernel linux-generic, casper, ubiquity, systemd, docker.io, podman, python3, nodejs 22, tailscale, etc
   - chroot: install council agents to /opt/council/
     ```bash
     /opt/council/
       hermes/ (uv venv + git clone NousResearch/hermes-agent)
       openclaw/ (npm install -g openclaw)
       codex/ (npm install @openai/codex)
       council-core/ (our orchestrator)
     ```
   - chroot: setup systemd units in /etc/systemd/system/council-*.service
   - chroot: create council user UID 1000, openclaw 1001, hermes 1002 (codex runs as the logged-in user - no container)
   - cleanup: truncate machine-id, apt clean, umount
3. Create ISO:
   - mksquashfs chroot/ image/casper/filesystem.squashfs -comp xz
   - Copy kernel/initrd
   - Create grub.cfg with: Try CouncilKey-Os, Install CouncilKey-Os, Check disc
   - EFI: efiboot.img FAT16 with bootx64.efi, grubx64.efi
   - BIOS: bios.img = cdboot.img + core.img
   - manifest, diskdefines, md5sum
   - xorriso -> councilkey-os-1.0-amd64.iso
4. Write to USB with persistence:
   ```bash
   dd if=councilkey-os-1.0-amd64.iso of=/dev/sdX bs=4M status=progress
   # Create persistence partition
   echo -e "n\n\n\n\nw" | fdisk /dev/sdX  # creates /dev/sdX3
   mkfs.ext4 -L casper-rw /dev/sdX3 -or- cryptsetup luksFormat /dev/sdX3 && mkfs.ext4
   # Boot flag: boot=casper persistent
   ```

**Result:** Bootable pendrive, 4-8GB ISO, persistence for agent memories.

### Profile 3: Immutable Bootc - Fedora (Advanced, Tank-OS style, most secure)

Based on Tank-OS:

- Base: quay.io/fedora/fedora-bootc:44
- **Containerfile**:
  ```dockerfile
  FROM quay.io/fedora/fedora-bootc:44
  RUN dnf install podman python3 nodejs 22 cloud-init openssh-server
  # Create 4 users with linger and subuid
  RUN useradd -u 1000 council && useradd -u 1001 hermes && useradd -u 1002 openclaw
  COPY rootfs/ /
  # rootfs has:
  # /etc/containers/systemd/users/1000/council-core.container
  # /etc/containers/systemd/users/1001/hermes.container
  # /etc/containers/systemd/users/1002/openclaw.container
  # codex runs as a local CLI (no container - no Docker)
  # /usr/local/bin/council
  ```
- Each .container is Quadlet unit pointing to:
  - `ghcr.io/openclaw/openclaw:latest`
  - `ghcr.io/nousresearch/hermes-agent:latest` (or custom)
  - codex CLI (npm @openai/codex)
  - `localhost/council-core:latest`
- Secrets via `podman secret`, not baked
- Build QCOW2/ISO/RAW via bootc-image-builder
- Output: councilkey.raw -> Etcher to USB
- Features: A/B rollback, can't brick, transactional upgrade via `bootc switch`

**Pros:** Enterprise-grade, most secure, Fedora.
**Cons:** Complex build, needs podman, 1-2 hour build.

---

## Persistence & Encryption

### Partition Layout (GPT recommended for UEFI)

```
/dev/sdX1: EFI System Partition, 512MB, FAT32, flags boot,esp, label COUNCIL_EFI
/dev/sdX2: Live partition, 8GB, ISO9660 / ext4 read-only, label COUNCIL_LIVE (contains squashfs or bootc)
/dev/sdX3: Persistence, rest of disk, LUKS2 encrypted ext4, label COUNCIL_PERSIST

Inside LUKS:
  /var/lib/council/
    hermes/ -> MEMORY.md, skills, SQLite FTS5 DB
    openclaw/ -> .openclaw/ soul.md, skills, memory DB
    codex/ -> CODEX_HOME state (history, config)
    shared/ -> shared memory.md, council journal git repo
    secrets/ -> podman secrets mount, 0600
    journal/ -> git repo of all council decisions: 2026-08-04-build-website.md etc
```

**Unlock flow:**
- At boot, `council-persistence.service` asks for passphrase (plymouth prompt) or auto-unlock via USB dongle keyfile (like Reefy: encryption keyed to USB dongle)
- Option: Shamir secret - need physical dongle + password

### No-Trace Mode
- `kernel cmdline: council.notrace` -> mounts tmpfs over persistence, no writes
- All TMPDIR, XDG_CACHE, npm-cache redirect to tmpfs

---

## Dashboard

Web UI at https://council.local:8443 (self-signed cert, LAN accessible offline like Reefy)

**Features:**
- Agent status: 3 cards showing Hermes/OpenClaw/Codex online/offline, CPU/RAM, current task
- Council chat: Input -> broadcast -> voting visualization -> final answer
- Journal: Git log of all council decisions, searchable via FTS5
- Skills: Browse installed skills for each agent, install from Hub
- Secrets: Add API keys via UI (writes to podman secret)
- System: Boot time, persistence usage, update button (bootc upgrade)

Tech: FastAPI + WebSocket + SQLite + vanilla JS (no heavy framework, fast boot)

---

## Security Model

From Tank-OS + Reefy analysis:

1. **No central docker daemon:** Use Podman rootless, no root privileges continuously
2. **User namespaces:** hermes UID 1001 maps to host 101001 via subuid
3. **Read-only root:** OS layer immutable, agents cannot modify system files
4. **Secret isolation:** Each agent's secrets only accessible to its own user via podman secret or 0600 file
5. **Approval gates:** Hermes has command approval, ClawOS policyd gates every tool call
6. **Quadlet isolation:** One agent compromise does not give access to others
7. **SBOM + cosign:** Build SBOM CycloneDX, sign images
8. **Offline first:** Works without internet for local models (Ollama, vLLM). Like Reefy, LAN access when internet down.

---

## First Boot Wizard

On first boot, TUI wizard (like openclaw onboard):

```
Welcome to CouncilKey-Os

1. Choose mode: [Portable] [Live] [Immutable]
2. WiFi setup: scan + connect
3. Agent API keys: Anthropic, OpenAI, Gemini, OpenRouter (or use Nous Portal)
   - Input hides typing, stored as podman secret
4. Create council admin password (for LUKS + dashboard)
5. Choose persistence: [Encrypted] [Unencrypted] [No persistence / Amnesiac]
6. Test: council ask "hello council" -> should get 3 agent responses + vote

Then reboot into fully working council.
```

---

## CLI

```bash
council status              # show 3 agents status
council ask "prompt"        # ask council
council vote --strategy majority "prompt"  # override strategy
council logs --agent hermes --tail 100
council shell hermes        # podman exec -it hermes sh
council secrets add anthropic_api_key
council update              # bootc upgrade or apt upgrade depending on profile
council build --profile live --arch amd64  # rebuild ISO
council flash /dev/sdX      # flash current build to USB
```

---

## Build Host Requirements

- Ubuntu 22.04+ or Fedora 40+
- 50GB disk
- 8GB RAM
- Packages: debootstrap, squashfs-tools, xorriso, grub, mtools, podman, nodejs 22, python3.11, uv

---

## Next Steps - See BUILD.md
