# Production Grade Audit - CouncilKey-Os

Date: 2026-08-04
Based on deep scan of Reefy OS (Buildroot production), Tank-OS (bootc production), Hermes SECURITY.md, OpenClaw fleet docs, plus our own code.

## What We Made (Current State)

### ✅ Strengths

1. **Deep Research**: 
   - Scanned 10 projects full code (portable-agent-usb, openclaw 310k stars, hermes-agent NousResearch, agent-zero, tank-os, reefy, magi, cx-distro, live-custom-ubuntu)
   - STORAGE_AUDIT.md: What makes agents smarter daily vs heavy junk to delete on unplug - from source code, not guesswork
   - OPTIMIZED_DESIGN.md: keep/cache split via tmpfs symlinks, wear leveling, LUKS

2. **Architecture**:
   - 3 partitions EFI FAT32 + LIVE squashfs RO + PERSIST LUKS2 encrypted
   - Council voting: majority, weighted, llm_judge, hermes_decides
   - Quadlet rootless Podman like Tank-OS
   - Dashboard v2 with 6 tabs: Council/Agents/Storage/Journal/Terminal/Secrets

3. **Build Profiles**:
   - Portable (5min, exFAT, cp -rL trick, no traces)
   - Live ISO (Ubuntu Noble from scratch, chroot+squashfs+grub BIOS/UEFI)
   - Bootc (Fedora immutable, A/B rollback, bootc-image-builder)

4. **Storage Optimizer Production Code**:
   - `council/storage/optimizer.py` 501 lines: audit(), what_if_delete(), optimize(), setup_persist_structure()
   - Handles tmpfs RAM auto delete on unplug, leaked cache detection, human_size, get_size
   - `cleanup.sh` deletes heavy on unplug, keeps smart
   - `council-storage-setup.sh` creates keep/cache split with symlinks

5. **Council Orchestrator v2**:
   - 423 lines, FastAPI dashboard, WebSocket, parallel broadcast like Tank-OS Quadlets, vote, journal git versioned
   - Health checks via socket port check

6. **Tests**: 11 passing (test_storage.py 6, test_council.py 5) after fixing PermissionError + KeyError

7. **Build System**:
   - Makefile with help, version, deps, build-portable/live/bootc/qcow2/raw/all, lint, test, security-scan, sbom, sign, verify, clean, release
   - VERSION file 1.0.0, pyproject.toml with dependencies, lint tools
   - GitHub Actions: pr.yaml (lint, test, build-bootc, security Trivy SARIF), release.yaml (build-and-push, SBOM, cosign sign, ISO artifact), scorecard.yaml OpenSSF

8. **Security Docs**: SECURITY.md with threat model, LUKS2, secrets never baked, rootless Quadlet, RO root, pinned versions CVE-2026-27002, SBOM+cosign, approval gates 2/3 vote

9. **Docs**: RESEARCH.md 19KB, ARCHITECTURE.md 15KB, BUILD.md, STORAGE_AUDIT.md, OPTIMIZED_DESIGN.md 13KB, PENDRIVE_GUIDE.md 17KB, FINAL_REPORT.md, SECURITY.md

### ❌ Gaps for Production Grade (What Needs Fix)

#### 1. **Real Agent Adapters - Currently Mock**
- **Current**: `AgentAdapter.ask()` checks if port open, returns mock if not. Vote is mock based on "danger" keyword.
- **Production Need**: Real HTTP adapters:
  - OpenClaw: POST http://localhost:18789/api/message with auth token from `~/.openclaw/gateway.token`, handle streaming, tool calls, file ops via Baileys/grammY
  - Hermes: `hermes gateway` API, FTS5 memory search, skill creation via `skills_list` + `skill_view`
  - Agent Zero: POST http://localhost:50001/api/message + file ops via `get_work_dir_files` API, LiteLLM provider abstraction
  - Implement `httpx` async client with timeout, retry, circuit breaker
  - LLM Judge for voting: Use Claude/GPT to judge best response

#### 2. **Containerfile Not Production Hardened**
- **Current**: Basic FROM fedora-bootc:44, installs podman, creates users, copies Quadlets, but no pinned versions for hermes/agent-zero, no CVE fix, no HEALTHCHECK, no SBOM, no non-root, no AppArmor.
- **Production Need**: Like Tank-OS Containerfile:
  ```dockerfile
  ARG FEDORA_BOOTC_BASE=quay.io/fedora/fedora-bootc:44
  ARG OPENCLAW_REF=2026.7.1 # Pinned for CVE-2026-27002
  ARG HERMES_REF=v1.2.3 # Need pin
  ARG AGENTZERO_REF=v0.8.1 # Need pin
  RUN dnf -y install ... ; dnf clean all; rm -rf /var/cache/dnf
  # Create users with linger + subuid like Tank-OS does
  # COPY rootfs/ with Quadlet units + council scripts 755 + sudoers 0440
  # HEALTHCHECK
  # LABEL containers.bootc=1 + org.opencontainers.image.source
  ```

#### 3. **Dashboard Not Production**
- **Current**: Vanilla JS, no auth, no HTTPS, no RBAC, no audit log, no xterm.js real terminal, just mock terminal.
- **Production Need**:
  - Auth: BasicAuth via `auth_login`/`auth_password` from Agent Zero settings pattern, or Tailscale (Reefy includes TAILSCALE_REEFY)
  - HTTPS: self-signed council.local cert like Reefy (devices issue own SSL certs)
  - RBAC: Admin vs user, pairing approval
  - Real terminal: xterm.js + websocket + `podman exec` via API, not mock
  - Audit log: Every council ask + vote + storage optimize logged to journal git + systemd journal
  - Monitoring: Agent CPU/RAM via `podman stats`, storage via `df`, exposed via `/api/metrics`

#### 4. **Storage Not Fully Production**
- **Current**: Optimizer works, but LUKS2 keyfile handling like Reefy not implemented (encryption keyed to USB dongle). Wear leveling only noatime,commit=60, but not f2fs (better for USB). No backup/restore.
- **Production Need**:
  - LUKS2 with keyfile on separate tiny USB dongle (Reefy: encryption keyed to USB dongle)
  - Choose FS: ext4 vs f2fs - f2fs better for USB wear but ext4 more compatible. Provide both options.
  - Backup: `council backup create` + `council backup restore` like Agent Zero backup API
  - Restore: `council backup preview` etc.

#### 5. **Build System Not Fully Production**
- **Current**: Makefile help exists, but no versioning from git tags, no semantic release python-semantic-release like Tank-OS, no per-arch manifest list.
- **Production Need**:
  - Semantic versioning via `python-semantic-release` like Tank-OS `pyproject.toml` + `commitlint.config.js`
  - Multi-arch manifest list: `podman manifest create` + `push --all`
  - QEMU smoke test in CI (like Tank-OS docs: `qemu-system-x86_64` + `grep login console.log`)
  - Output SBOM always

#### 6. **Observability Missing**
- **Current**: No health checks, no systemd watchdog, no log rotation, no metrics.
- **Production Need**:
  - Quadlet HEALTHCHECK: `HealthCmd=CMD-SHELL curl -f http://localhost:8443/api/status || exit 1`
  - systemd watchdog: `WatchdogSec=30` + `Restart=on-failure`
  - Log rotation: `journald.conf.d/size-limit.conf` like Reefy (size-limit.conf)
  - Metrics: `/api/metrics` returns CPU/RAM/storage per agent

#### 7. **Docs Missing for Production**
- Need API docs OpenAPI (FastAPI auto generates /docs), threat model, ADRs, runbook for on-call.

## Production Grade Roadmap - What We Will Implement Now

### Phase 1: Fix Tests + Real Adapters (Today)

- [x] Tests passing 11/11
- [ ] Real HTTP adapters for 3 agents using httpx async, with fallback mock if offline (production graceful degradation)
- [ ] LLM Judge voting using LiteLLM (like Agent Zero uses litellm==1.88.1)
- [ ] Storage optimizer already production, but fix COUNCIL_HOME dynamic read (done)

### Phase 2: Hardened Containerfile + Makefile + CI (Today)

- [ ] Containerfile with pinned versions, CVE fix comment, HEALTHCHECK, LABEL, non-root, clean dnf cache
- [ ] Makefile with semantic release, multi-arch, sbom, sign, verify, security-scan
- [ ] GitHub Actions already created, but need to test in CI

### Phase 3: Dashboard Production (Today)

- [ ] Auth via BasicAuth or Tailscale
- [ ] Real terminal via xterm.js + WebSocket + podman exec (not mock)
- [ ] Metrics endpoint + storage bar real data
- [ ] HTTPS self-signed

### Phase 4: Storage Production (Today)

- [ ] LUKS2 keyfile handling doc + script (Reefy style)
- [ ] Backup/restore via council backup create/restore/preview
- [ ] F2FS option + ext4 noatime

### Phase 5: Docs Production

- [ ] API.md from FastAPI OpenAPI
- [ ] PRODUCTION.md with runbook
- [ ] SECURITY.md already exists but need threat model diagram

## What we have vs Production Grade Score

| Category | Current | Production Target | Score |
|----------|---------|-------------------|-------|
| Research | 10 projects scanned full code | + CVE, threat model, ADRs | 8/10 |
| Storage Optimizer | audit/what-if/optimize/setup working, tests pass | + LUKS keyfile dongle, f2fs, backup/restore | 7/10 |
| Council Core | Mock responses, voting mock | + Real HTTP adapters, LLM judge, LiteLLM | 5/10 |
| Dashboard | 6 tabs, vanilla JS, mock terminal | + Auth, RBAC, xterm.js real, HTTPS, metrics | 6/10 |
| Containerfile | Basic Fedora bootc + Quadlets | + Pinned versions CVE fix, HEALTHCHECK, LABEL, non-root, SBOM | 5/10 |
| Makefile | Help, version, build, lint, test, sbom, sign | + Semantic release, multi-arch manifest, QEMU smoke test | 7/10 |
| CI/CD | pr.yaml, release.yaml, scorecard.yaml created | + Need to test in real GitHub, add dependabot | 6/10 |
| Security | SECURITY.md threat model, LUKS, secrets not baked, rootless, RO root | + AppArmor, Secure Boot shim, Tailscale | 7/10 |
| Tests | 11 passing | + More coverage council voting, storage edge cases, integration QEMU | 7/10 |
| Docs | 7 docs 100KB total | + API.md, PRODUCTION.md runbook, ADRs | 7/10 |

**Overall: 6.5/10 -> Need to reach 9/10 for production grade**

## Next Steps Now

We will:

1. Implement real agent adapters (HTTP) with fallback mock (graceful degradation production pattern)
2. Harden Containerfile with pinned versions, HEALTHCHECK, LABEL, CVE comments
3. Enhance Makefile with semantic release + multi-arch
4. Enhance dashboard with real metrics + auth placeholder
5. Create PRODUCTION.md + API.md
6. Re-run tests to ensure all pass
7. Final commit + push
