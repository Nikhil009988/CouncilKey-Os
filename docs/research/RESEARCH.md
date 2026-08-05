# CouncilKey-Os Research Report
# How existing Live AI OS projects work - full code scan

This document is the result of scanning 7+ open source projects that build live Linux / portable USB OS with AI agents.

Date: 2026-08-04

---

## 1. Projects Analyzed

| Project | Repo | Stars | Approach | Language |
|---------|------|-------|----------|----------|
| **portable-agent-usb** | bnovik0v/portable-agent-usb | ~7 | Portable exFAT USB, no install | Bash |
| **OpenClaw** | openclaw/openclaw | 310k | AI assistant Node.js gateway | TS/JS |
| **Hermes Agent** | NousResearch/hermes-agent | ? | Self-improving Python agent | Python |
| **Agent Zero** | agent0ai/agent-zero | 10k+ | Prompt-based framework, Docker | Python |
| **Tank-OS** | LobsterTrap/tank-os | Red Hat | bootc immutable OS + Quadlet | Containerfile + Bash |
| **Reefy OS** | reefyai/reefy | 458 | Buildroot minimal OS, 15s boot | Buildroot Kconfig + Shell |
| **MAGI OS** | ruapotato/MAGI | ? | Debian + MATE AI desktop | Python/Shell |
| **CX Linux** | cxlinux-ai/cx-distro | ? | Debian live-build AI-native | Shell + live-build |
| **live-custom-ubuntu-from-scratch** | mvallim/live-custom-ubuntu-from-scratch | popular | chroot+squashfs+casper | Bash |
| **ClawOS** | xbrxr03/clawos | new | Ubuntu/Debian installer + Ollama | Bash |

---

## 2. Deep Dive - How Each Works

### 2.1 portable-agent-usb - The simplest live idea

**Path:** `/tmp/scan/portable-agent-usb`

**Core idea:** Not a bootable OS, but a USB drive that IS the OS for agents. No installation, no traces.

**Build flow (`setup.sh`):**
```bash
USB=/mnt/usb
NODE_VERSION=22.14.0
- creates /bin/{win,linux}, /tools/{win,linux}/{claude-code,codex}, /config/.claude, /temp
- Downloads Node.js linux-x64 tar.xz and win-x64 zip
- CRITICAL: exFAT has no symlinks, so it does cp -rL (resolve symlinks to real files)
- Uses staging dir /tmp/portable-agent-staging to npm install, then copy_resolved to USB
- Installs @anthropic-ai/claude-code and @openai/codex via staging Node
- Copies launcher scripts start.sh / start.bat
- Creates env.sh / env.bat with API keys
- Syncs and verifies ELF binary + .bin files
```

**Runtime (`start.sh`):**
- Finds latest node-v*-linux-x64 dynamically
- Exports PATH to portable node + claude/codex bin
- Sources config/env.sh
- Exports CLAUDE_CONFIG_DIR to USB/config/.claude
- **KEY TRICK:** Redirects all temp/cache to USB:
  ```bash
  export TMPDIR=$USB/temp
  export NPM_CONFIG_CACHE=$USB/temp/npm-cache
  export XDG_CONFIG_HOME=$USB/config
  ```
- Then `exec bash --norc --noprofile` - clean shell with portable env

**How to adapt for CouncilKey:**
- Extend bin/linux, tools/linux to include 3 agents: hermes, openclaw, agent-zero
- Node 22.14 for openclaw, Python venv for hermes & agent-zero must also be portable and resolved symlinks
- Same TMPDIR trick ensures host stays clean

**Weakness:** Needs host OS (Windows/Linux). Not a true bootable Live Linux. But fastest to test.

---

### 2.2 OpenClaw - The agent itself

**Path:** `/tmp/scan/openclaw-code`

**Structure scanned:**
- `apps/` - desktop, control-ui, etc
- `extensions/` - skills, plugins
- `docs/` - installation, security, architecture
- Main is Node.js global package: `npm install -g openclaw@latest`
- Requires Node >=22.19, recommends Node 24

**How it runs:**
```bash
openclaw onboard --install-daemon  # installs systemd user service, gateway on 18789
openclaw gateway status
openclaw dashboard
openclaw gateway start
```
- Stores data in `~/.openclaw/`: soul.md (personality), .env (API keys), skills/, data/ (memory DB), logs/
- Gateway: single process that bridges models + tools + messaging channels (Telegram Bot API via grammY, WhatsApp via Baileys, Discord Bot API, Signal, etc)
- Model agnostic: Claude, GPT, local Ollama, Kimi k2.5
- Skills: 100+ preconfigured AgentSkills, each can execute shell, file ops, web automation
- Security: 50-100MB idle, binding gateway to loopback only, pairing approval via `openclaw pairing approve <channel> <code>`

**Installation details from code:**
- Uses PM2 or systemd for always-on
- Works in WSL2, Docker, Nix
- For Tank-OS it runs as rootless Podman container with secret handling

**Key file for CouncilKey:** We need to install global npm, then run onboard but point OPENCLAW_HOME to /opt/council/openclaw/data or USB.

---

### 2.3 Hermes Agent - Nous Research

**Path:** `/tmp/scan/hermes-agent`

**Repo structure:**
```
hermes-agent/
  src/hermes_agent/ - core python package
    tools/ - 40+ tools (terminal, file, browser, code_execution, vision, tts, delegation)
    models/ - provider abstraction for 300+ models (via Nous Portal)
    monitors/ - system monitoring
    widgets/ - GUI components (for desktop app)
  apps/desktop/ - Electron/Tauri native desktop app (macOS, Win, Linux)
  website/docs/ - extensive docs
  scripts/install.sh - curl | bash installer
  prompts/ - system prompts that define behavior
  skills/ - skill system with YAML frontmatter
  knowledge/ - persistent memory system
```

**Architecture insights from evaluation doc:**
- **Tool Registry:** ~50 built-in tools, self-register at import time
- **Memory:** File-backed MEMORY.md + USER.md frozen into system prompt at session start, with injection/exfiltration scanning
- **Skills:** Markdown + YAML frontmatter, nearly identical to Claude Code SKILL.md. Self-improving: agent can generate and refine skills after complex tasks
- **Gateway:** 15+ platform adapters with session persistence and voice memo transcription. Most distinctive component vs Claude Code.
- **Session Store:** SQLite with WAL mode, FTS5 full-text search across all messages
- **Context Compression:** Auto-compresses middle turns, protects head/tail, uses auxiliary model for summarization
- **Subagent Delegation:** Spawns child agents with isolated context, restricted toolsets, max depth 2, 3 concurrent
- **MCP Client:** ~1050 lines, stdio+HTTP, auto-reconnect, thread-safe, OSV checking
- **Execution Backends:** 7 backends - local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox. Daytona/Modal hibernate when idle.
- **Trajectory/RL:** JSONL trajectory saving, compression, Atropos RL integration - for training next gen models

**Install (`install.sh`):**
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
- Handles Git prereq only, everything else via uv
- Creates ~/.hermes/ with venv via uv venv --python 3.11
- Creates ~/.hermes/hermes-agent checkout
- Installs via uv pip install -e ".[all]"
```

**Runtime:**
- CLI: `hermes` -> full TUI with multiline editing, slash-command autocomplete, streaming tool output
- Gateway: `hermes gateway setup` + `hermes gateway start` -> bridges Telegram, Discord, Slack, WhatsApp, Signal
- Desktop: `hermes desktop` builds GUI against existing install

**CouncilKey adaptation:**
- Needs Python 3.11 + uv. Portable venv must be in /opt/council/hermes/.venv and have `uv` binary bundled
- Config lives in ~/.hermes/
- Should expose 2 services: hermes CLI and hermes gateway

---

### 2.4 Agent Zero - agent0ai/agent-zero

**Path:** `/tmp/scan/agent-zero`

**Philosophy:** The MOST minimal and hackable. Whole framework behavior lies in `prompts/` folder. Not pre-programmed.

**Scanned structure:**
```
agent-zero/
  agent.py - main loop
  initialize.py - setup
  run_ui.py - WebUI
  models.py - model abstraction
  prompts/ - system prompts that ARE the framework
  agents/ - profiles: default, agent0, developer, hacker, researcher, tiny-local, _example
    each has agent.yaml + prompts/
  tools/ - basic tools, but agent can write its own tools on demand
  api/ - 100+ API endpoints (chat, history, file ops, mcp, scheduler, backup)
  webui/ - frontend
  extensions/ - plugin system
  docker/ - Docker environment
  knowledge/ - persistent memory files
  plugins/ - community plugins
```

**How it works:**
- `python agent.py` -> starts loop, uses OS as tool (terminal, code exec, file creation)
- Can download docker image `frdel/agent-zero-exe` and run itself containerized
- WebUI via `run_ui.py` -> browser DOM annotation, live document cowork (Markdown, Writer, Spreadsheet, Presentation), full Linux desktop via Canvas
- Plugin Hub: 100+ community plugins
- Multi-agent cooperation: delegates to focused subagents
- Host-machine bridge via A0 CLI so same agent works in real local repos
- Prompt-based: rewrite whole behavior in prompts/ folder
- Memory: persistent, memorizes previous solutions

**Requirements:** Python, Docker optional

**CouncilKey adaptation:**
- Easiest to bundle - just clone repo to /opt/council/agent-zero, pip install -r requirements.txt in venv
- Runs on port ~50001 or configurable, WebUI

---

### 2.5 Tank-OS - Bootable container OS (most relevant for live USB CouncilKey)

**Path:** `/tmp/scan/tank-os`

**Author:** Sally O'Malley, Red Hat Principal Engineer, OpenClaw core maintainer

**Core idea:** Pack Agent + Runtime + OS + Systemd units + Upgrade mechanism into single OCI container image, then boot entire machine directly from that image.

**Tech stack:**
- Base: `quay.io/fedora/fedora-bootc:44` (Fedora 44 bootc)
- `bootc` - transforms container images into bootable, updatable Linux OS images
- `rootless Podman Quadlet` - OpenClaw runs without underlying system privileges
- `cloud-init` for SSH key injection on EC2/GCP/Raspberry Pi
- `bootc-image-builder` to create disk images: QCOW2, ISO, raw

**Containerfile scanned:**
```dockerfile
FROM quay.io/fedora/fedora-bootc:44
LABEL containers.bootc=1
RUN dnf -y install cloud-init curl openssh-server podman python3 qemu-guest-agent shadow-utils sudo vim-enhanced
# Install OpenShell RPMs (NVIDIA OpenShell)
# Create openclaw user UID/GID 1000, enable linger, configure subuid/subgid 100000-165535 for rootless Podman
useradd -m -u 1000 -g 1000 openclaw
COPY rootfs/ /
# rootfs contains:
# /etc/containers/systemd/users/1000/openclaw.container  <- Quadlet unit
# /usr/local/bin/openclaw, tank-os-version, tank-openclaw-secrets
# /usr/libexec/tank-os/bootstrap-*
# Enable sshd.service + cloud-init services
```

**Quadlet definition:** `/etc/containers/systemd/users/1000/openclaw.container` -> Image=quay.io/redhat-et/tank-claw-openshell:2026.7.1

**Secrets handling (critical):**
- Do NOT bake API keys into image
- Use `podman secret create anthropic_api_key -` from stdin
- Then `tank-openclaw-secrets` syncs secrets to container
- Supported: anthropic_api_key, openai_api_key, gemini_api_key, gh_token

**Build flow:**
```bash
make build-openclaw-openshell # Build derived OpenClaw+openshell image first
make push-openclaw-openshell
make build  # Build bootc container image localhost/tank-os:latest
make build-qcow2 # Needs config.toml + bootc-image-builder container
# Output: out-tank-os/qcow2/disk.qcow2
```

**QCOW2 build via bootc-image-builder:**
```bash
podman run --rm --privileged \
  -v ./out-tank-os:/output \
  -v ./config.toml:/config.toml:ro \
  -v /var/lib/containers/storage:/var/lib/containers/storage \
  quay.io/centos-bootc/bootc-image-builder:latest \
  localhost/tank-os:latest --output /output/ --local --type qcow2 --target-arch amd64 --rootfs xfs --config /config.toml
```

**Boot:**
- QEMU: qemu-system-x86_64 -drive file=out-tank-os/qcow2/disk.qcow2,format=qcow2,if=virtio
- Physical: flash raw image to USB via Balena Etcher or dd
- Login: ssh -p 2222 openclaw@localhost (or console)
- State: /var/home/openclaw/.openclaw

**Upgrade model - A/B transactional:**
```
Running image v1.0 (read-only mounted) -> bootc switch quay.io/sallyom/tank-os:v1.1 -> Download new layers to standby partition -> Reboot -> atomic switch -> Error -> bootc rollback -> back to v1.0
```
Immutable OS, can't brick, auto-rollback via hardware watchdog.

**CouncilKey take:** This is the GOLD STANDARD for CouncilKey-Os if we want enterprise-grade, secure, multi-agent isolation. Each agent could be its own Quadlet container with no shared credentials, all running rootless, OS read-only.

---

### 2.6 Reefy OS - Buildroot from scratch

**Path:** `/tmp/scan/reefy`

**Core idea:** Not Ubuntu/Debian shell + web UI. Built from Buildroot, hand-picked every package from kernel up.

**Key features scanned:**
- 15-second cold boot (optimized kernel and early boot services)
- Nvidia GPU as first-class citizen
- Immutable A/B root with auto-rollback
- Encryption keyed to USB dongle
- No package manager on device (no drift)
- App catalog AI-focused from day one: OpenClaw, Hermes, Ollama, vLLM, SGLang, vision pipelines

**Build system:**
- Submodule buildroot at ffbffae
- Config: `configs/reefy_defconfig` -> 200+ Buildroot Kconfigs scanned:
  ```kconfig
  BR2_INIT_SYSTEMD=y
  BR2_LINUX_KERNEL=y
  BR2_LINUX_KERNEL_CUSTOM_GIT=y
  BR2_LINUX_KERNEL_CUSTOM_REPO_VERSION="v6.18.40"
  BR2_PACKAGE_DOCKER_ENGINE=y
  BR2_PACKAGE_TAILSCALE_REEFY=y
  BR2_TARGET_ROOTFS_SQUASHFS=y
  BR2_PACKAGE_NVIDIA_OPEN_GPU=y
  etc
  ```
- `board/reefy/reefy/` contains:
  - `rootfs-overlay/etc/` -> docker/daemon.json, profile.d/, reefy/, systemd/ (docker.service.d, docker.slice, network), wpa_supplicant
  - `pre_build.sh`, `post_build.sh`, `post_image.sh` -> scripts to customize rootfs
  - `kernel-config`, `kernel-config-wifi`
- `containers/` -> app containers (openclaw, ollama, etc)
- `package/` -> custom Buildroot packages
- `scripts/` -> install-linux.sh, install-mac.sh, reefy-start-vm.sh etc

**Workflow:**
```bash
# At reefy.ai you log in with Google/GitHub, get personalized device image
# Or build locally via Buildroot make
Make reefy_defconfig + make
# Output: reefy.raw -> flash via Balena Etcher
# Boot any x86, 15 sec, appears in reefy.ai dashboard, click Adopt
```

**Security by design:** Minimal host, immutable A/B firmware, LTS kernel, encrypted storage, containerized apps, publicly traceable builds.

**CouncilKey take:** If we want absolute fastest boot and personal cloud-like experience, Buildroot is best but most complex. Requires building kernel, toolchain, etc. 2-3 hour build. But produces tiny, secure image.

---

### 2.7 MAGI OS + CX Linux + live-custom-ubuntu-from-scratch - Debian/Ubuntu live path

**These three share same DNA: live-build / debootstrap + chroot + squashfs.**

**live-custom-ubuntu-from-scratch flow (canonical):**
```bash
# Host = build system, Target = live system
1. Prepare env: sudo apt install debootstrap squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin mtools dosfstools
2. debootstrap --arch=amd64 noble chroot http://archive.ubuntu.com/ubuntu/
3. Mount: mount --bind /dev chroot/dev; mount -t proc /proc chroot/proc etc
4. Chroot: LANG=C chroot chroot /bin/bash
   - apt install linux-generic casper ubiquity etc + custom packages
   - Configure user, systemd, etc
5. Cleanup chroot: truncate machine-id, apt clean, umount
6. Prepare image/ dir:
   - mksquashfs chroot image/casper/filesystem.squashfs
   - cp chroot/boot/vmlinuz, initrd to image/casper/
   - Create image/isolinux/grub.cfg with entries: Try Ubuntu without installing, Install
   - Create EFI boot: dd efiboot.img + mkfs.vfat + mcopy bootx64.efi, grubx64.efi
   - Create BIOS boot: grub-mkstandalone + cat cdboot.img + core.img -> bios.img
   - Create manifest: dpkg-query -W > filesystem.manifest
   - Create diskdefines
   - md5sum
7. ISO: xorriso -as mkisofs -iso-level 3 -o custom.iso -isohybrid-mbr -b isolinux/bios.img -c isolinux/boot.cat -eltorito-alt-boot -e isolinux/efiboot.img -no-emul-boot -isohybrid-gpt-basdat image
8. Write to USB: dd if=custom.iso of=/dev/sdX bs=4M status=progress
```

**CX Linux adds:**
- APT repository with signed packages (cx-core minimal, cx-full complete)
- Preseed automation for unattended install
- SBOM (CycloneDX/SPDX)
- Scripts/build.sh offline -> live-build wrapper

**MAGI OS adds:**
- Based on Debian + MATE/GTK
- bin/setup.sh for local install, bin/build.sh for ISO (requires root)
- src/magi_shell/ with core/, models/, monitors/, widgets/
- Config in ~/.config/magi/config.json

**All:** Produce bootable ISO that can be dd-ed to pendrive. Support persistence via casper-rw partition (ext4) with boot=casper persistent flag.

**For CouncilKey:** This is the classic, most documented route. Easiest for community to understand and modify. We can start here.

---

## 3. Common Patterns Across Projects

1. **Immutable / Read-only root:** Tank-OS, Reefy both use read-only root + A/B rollback. Prevents agent from corrupting host.
2. **Rootless container isolation:** Tank-OS uses rootless Podman Quadlet, each agent isolated, credentials via secrets, not files.
3. **Data on USB / Separate partition:** All use separate persistent partition so agents memories survive reboot.
4. **Cloud-init / First-boot provisioning:** Tank-OS and Reefy use cloud-init for SSH key injection, WiFi, etc.
5. **Copy-resolving symlinks for exFAT:** portable-agent-usb solves exFAT limitation.
6. **Cache redirection:** Redirect all caches to USB to leave no traces and survive.
7. **Secret management:** Never bake API keys into image. Use runtime secret injection (podman secret, env.sh, portal OAuth).
8. **Fast boot optimization:** Reefy optimized kernel early boot, systemd critical-chain analysis.
9. **Dashboard:** Reefy has reefy.ai dashboard, OpenClaw has Control UI on 18789, Agent-Zero has WebUI, Hermes has Desktop app.
10. **Multi-arch:** Most build both amd64 and arm64.

---

## 4. CouncilKey-Os Recommended Stack

For a council of 3 agents live in one pendrive, we recommend **hybrid approach**:

**Phase 1: Portable (Week 1):** Like portable-agent-usb - exFAT pendrive, portable Node.js + Python uv, 3 agents bundled, start.sh launches council dashboard.

**Phase 2: Live ISO (Month 1):** Like live-custom-ubuntu-from-scratch - Ubuntu 24.04 base, casper live, persistence partition, systemd services for 3 agents, council orchestrator.

**Phase 3: Immutable Bootc (Month 2):** Like Tank-OS - Fedora bootc base, 3 Quadlet containers (hermes, openclaw, agent-zero) + council-core container, A/B rollback, encryption keyed to USB.

**Final Architecture:**
- Base OS: Fedora bootc for security OR Ubuntu live for simplicity (provide both profiles)
- Agent isolation: Rootless Podman, each agent UID 1000/1001/1002, subuid ranges separate
- Council orchestration: Python service that proxies user input to all 3, gathers responses, voting (majority, weighted, or LLM-as-judge)
- Persistence: LUKS encrypted partition on pendrive, mounted at /var/lib/council/
- Dashboard: Web UI at https://council.local - shows each agent status, conversation, council votes
- First boot: cloud-init or setup wizard asking for API keys, WiFi
- No trace mode: TMPDIR to pendrive, overlayfs

---

## 5. Security Considerations from Code Scan

- **CVE-2026-27002 fixed in Tank-OS** - sandbox bind-mount escape chain. Shows need to pin versions, not use latest.
- **OpenClaw remote attack surface:** Gateway must bind to 127.0.0.1 only, not 0.0.0.0, unless behind Tailscale.
- **Agent data deletion:** Real incidents - OpenClaw agents deleted emails, modified data. Council voting can mitigate.
- **Credential leakage:** APIs keys in config files readable by other processes. Use podman secrets with 0600.
- **Supply chain:** Reefy uses publicly traceable builds, SBOM, cosign signing. CouncilKey should too.

---

## Next: See ARCHITECTURE.md for actual design.
