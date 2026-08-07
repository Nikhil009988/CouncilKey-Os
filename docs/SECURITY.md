# CouncilKey-Os Security

Based on deep scan of Hermes SECURITY.md + Tank-OS CVE-2026-27002 + Reefy security by design.

## Threat Model

**Single-tenant personal agent** - same as Hermes posture: The only security boundary against adversarial LLM is OS-level isolation.

### What we protect:

- **Persistence partition LUKS2 encrypted**: All keep/ smart data + secrets/ encrypted at rest. Master key itself LUKS protected + optional keyfile on separate tiny USB dongle (Reefy style).
- **Secrets never baked into ISO**: Like Tank-OS, we use `podman secret create` + GPG encrypted files in `secrets/` 700. ISO contains no API keys.
- **Rootless Podman Quadlet**: No docker daemon running as root continuously. Each agent UID 1000-1003 maps to host 100000+ via subuid/subgid. Container root is unprivileged user on host.
- **Read-only root**: Squashfs live + bootc immutable A/B, OS layer read-only, agents cannot modify system files, rollback on failure via `bootc rollback`.
- **Approval gates**: Hermes command approval, OpenClaw pairing approval, ClawOS policyd gates every tool call, sensitive actions require 2/3 council vote (prevents OpenClaw email deletion incident from Tank-OS docs).
- **Supply chain**: Pinned versions (OPENCLAW_REF=2026.7.1 fixes CVE-2026-27002 sandbox bind-mount escape chain, HERMES_REF pinned, OPENCODE_REF pinned (npm opencode-ai)), SBOM CycloneDX/SPDX, cosign signing, Trivy scanning.

### What we DON'T protect (in-process heuristics not boundary):

- Approval gate, output redaction, pattern scanners, tool allowlists inside agent process are heuristics on attacker-influenced string, not containment.
- Terminal backend isolation vs whole-process wrapping: We use whole-process wrapping (rootless Podman Quadlet) for all agents, not just terminal backend.

## Reporting Vulnerability

Privately via GitHub Security Advisories, not public issues. Include file path + line range, env details, reproduction against main.

## Security Features Implemented

### 1. Encryption

- LUKS2 for persistence (`/dev/sdX3` label casper-rw/COUNCIL_PERSIST), `cryptsetup luksFormat` with passphrase + optional keyfile on separate tiny USB dongle (Reefy `config.toml` can embed key? No, we use separate file).
- GPG encrypted secrets in `secrets/*.gpg` with master.key LUKS protected.
- `noatime,commit=60,discard` for wear leveling + performance, `encrypt` for f2fs option if using f2fs instead of ext4 (for USB wear).

### 2. Secrets Management (from Tank-OS scan)

```bash
# Never bake keys into image
printf '%s' "$ANTHROPIC_API_KEY" | podman secret create anthropic_api_key -
printf '%s' "$OPENAI_API_KEY" | podman secret create openai_api_key -
printf '%s' "$GH_TOKEN" | podman secret create gh_token -
# Then tank-openclaw-secrets syncs to container (we have council-secrets)
tank-openclaw-secrets && systemctl --user restart openclaw.service

# Our council version:
council secrets add anthropic_api_key  # prompts secure input, no echo, writes to podman secret + gpg
council secrets list  # shows which keys set, not values
```

### 3. Isolation

- Quadlet: `openclaw.container`, `hermes.container`, `council-core.container` each rootless (opencode runs as a local CLI - no container, no Docker), separate UID, no shared credentials, cannot access other programs on host.
- User namespace isolation: subuid 100000-165535 for council, 165536-231071 for hermes, etc.
- Firewall: UFW or firewalld, only allow 8443 (dashboard), 18789 (openclaw gateway loopback only), 18790 (hermes loopback only). Dashboard binds 0.0.0.0 for LAN like Reefy (LAN access when internet down), but gateway binds 127.0.0.1 only unless behind Tailscale.

### 4. Pinned Versions (CVE fix)

From Tank-OS commit: Pinned to tagged release, not main/latest, because specific version fixes CVE-2026-27002 and sandbox bind-mount escape chain. We do same:

```dockerfile
ARG OPENCLAW_REF=2026.7.1
ARG HERMES_REF=v1.2.3  # pinned
ARG OPENCODE_PACKAGE=opencode-ai # pinned via npm
```

### 5. SBOM + Signing

Makefile targets:
- `make sbom` -> syft generates CycloneDX JSON + SPDX JSON in `output/sbom/`
- `make sign` -> cosign sign --key env://COSIGN_PRIVATE_KEY image:version
- `make verify` -> cosign verify
- `make security-scan` -> trivy image

GitHub Actions (see `.github/workflows/`) runs Trivy weekly, uploads SARIF to GitHub Security.

### 6. Dashboard Auth

- v1: No auth (LAN only, like Reefy)
- Production: Add BasicAuth via `auth_login` `auth_password`, or OAuth via Tailscale (Tailscale is BR2_PACKAGE_TAILSCALE_REEFY in Reefy defconfig, we include it)
- Secrets edit via GPG in dashboard requires master password (LUKS passphrase)

### 7. Audit Logging

- Journal is git versioned, but also systemd journal for services: `journalctl -u council-* -f`
- Council decisions log to journal with timestamp, votes, prompt hash
- Storage optimizer logs saved human-readable

## Deployment Checklist

- [x] LUKS2 encrypted persistence
- [x] Secrets never baked into image, podman secret + GPG
- [x] Rootless Quadlet isolation, subuid/subgid
- [x] Read-only root, A/B rollback via bootc
- [x] Pinned versions for CVE
- [x] SBOM generation
- [x] Cosign signing/verify
- [x] Trivy scanning
- [x] Approval gates + 2/3 vote for sensitive
- [x] Dashboard LAN offline access
- [x] Cleanup on unplug deletes heavy cache, keeps smart
- [x] Noatime, commit=60 wear leveling
- [ ] Secure Boot with shim (currently requires disabling Secure Boot, future: sign shim with own key)
- [ ] F2FS for USB instead of ext4 (better wear leveling, but ext4 with noatime ok for 1.0)
- [ ] Tailscale for remote access (included in builder but not yet auto-configured)
- [ ] AppArmor/SELinux profiles for each Quadlet

## For Contributors

- Never commit secrets to git, use `config/env.sh.example`
- Run `make lint` before PR
- Run `make security-scan` before release
- Update `VERSION` file for semantic release
- PR title must follow conventional commits for semantic release (feat:, fix:, BREAKING CHANGE:)
