# CouncilKey-Os - Build Guide

This guide gives you 3 ways to build CouncilKey-Os - portable, live ISO, and immutable bootc.

---

## Quick Start - Portable USB (5 minutes, no reboot)

This is fastest to test the 3-agent council on any PC, Windows/Linux.

**Requirements:**
- USB drive 16GB+ formatted exFAT
- Linux host with curl, unzip, nodejs local optional
- Or Windows with Node.js

**Build:**
```bash
git clone https://github.com/Nikhil009988/CouncilKey-Os
cd CouncilKey-Os
chmod +x scripts/build-portable.sh
./scripts/build-portable.sh /mnt/your-usb-drive
# Example: /media/$USER/COUNCIL or /mnt/e if WSL
```

What the script does:
- Downloads Node.js 22.14 for Linux+Windows (handles exFAT no-symlink via cp -rL)
- Downloads Python 3.11 portable + uv
- Installs:
  - OpenClaw: npm install -g openclaw@latest to tools/linux/openclaw
  - Hermes: git clone NousResearch/hermes-agent + uv venv to tools/linux/hermes
  - Agent-zero: git clone agent0ai/agent-zero to tools/linux/agent-zero
  - Council Core: our orchestrator to tools/linux/council-core
- Creates config/ templates for API keys
- Copies launcher scripts start.sh / start.bat

**Use:**
```bash
# Linux
bash /media/$USER/COUNCIL/start.sh
# Then:
council status
council ask "hello council, introduce yourselves"
# Type 'hermes' for Hermes TUI, 'openclaw' for OpenClaw, 'agent-zero' for Agent Zero

# Windows
Double-click start.bat
```

No traces left on host - all temp/cache to USB/temp.

---

## Live ISO - Ubuntu Noble 24.04 (30-60 minutes, produces bootable pendrive)

Based on mvallim/live-custom-ubuntu-from-scratch.

**Build host:** Ubuntu 22.04+/24.04+ VM with 50GB free, 8GB RAM, internet.

**Install deps:**
```bash
sudo apt update
sudo apt install -y debootstrap squashfs-tools xorriso isolinux syslinux-efi grub-pc-bin grub-efi-amd64-bin mtools dosfstools dpkg-dev devscripts debhelper fakeroot gnupg curl wget git live-build
```

**Build:**
```bash
git clone https://github.com/Nikhil009988/CouncilKey-Os
cd CouncilKey-Os
sudo chmod +x scripts/build-live-iso.sh
sudo ./scripts/build-live-iso.sh noble
# Args: [codename] [arch] [output dir]
# codename: noble (24.04) recommended, jammy (22.04) also works
# Output: output/councilkey-os-1.0-noble-amd64-live.iso
```

**What build-live-iso.sh does step by step:**
1. `debootstrap --arch=amd64 noble chroot http://archive.ubuntu.com/ubuntu/`
2. Mount bind: /dev, /run, and chroot mounts: chroot proc/sys/dev/pts
3. Chroot and install:
   - linux-generic, linux-firmware, casper, ubiquity, ubiquity-casper
   - systemd, network-manager, wireless-tools, wpasupplicant
   - docker.io, podman, python3, python3-pip, python3-venv, curl, git, sudo, etc
   - Node.js 22 via nodesource: curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
   - Council agents to /opt/council/:
     ```bash
     /opt/council/hermes - uv + hermes-agent
     /opt/council/openclaw - npm install -g openclaw
     /opt/council/agent-zero - clone + pip install -r requirements.txt
     /opt/council/council-core - pip install fastapi uvicorn
     ```
4. Setup systemd units from council/systemd/*.service to /etc/systemd/system/
   - council-hermes.service -> ExecStart=/opt/council/hermes/.venv/bin/hermes gateway start
   - council-openclaw.service -> ExecStart=/usr/bin/openclaw gateway start
   - council-agentzero.service -> ExecStart=python3 /opt/council/agent-zero/run_ui.py --host 0.0.0.0 --port 50001
   - council-core.service -> ExecStart=python3 /opt/council/council-core/main.py
5. Create council user (UID 1000), hermes 1001, openclaw 1002, agent0 1003, set linger, subuid/subgid
6. Cleanup chroot: truncate /etc/machine-id, apt clean, rm /tmp/*, umount
7. Prepare image/:
   - mksquashfs chroot image/casper/filesystem.squashfs -comp xz -e boot
   - cp chroot/boot/vmlinuz-* image/casper/vmlinuz
   - cp chroot/boot/initrd.img-* image/casper/initrd
   - Create image/isolinux/grub.cfg (see builder/live/grub.cfg template)
   - EFI boot: dd efiboot.img 10M, mkfs.vfat, mcopy bootx64.efi, mmx64.efi, grubx64.efi, grub.cfg
   - BIOS boot: grub-mkstandalone --format=i386-pc --output=isolinux/core.img ...
   - cat cdboot.img + core.img -> bios.img
   - Create filesystem.manifest: dpkg-query -W > filesystem.manifest
   - Create filesystem.manifest-desktop (remove casper, ubiquity, etc)
   - Create README.diskdefines
   - md5sum
8. ISO: xorriso -as mkisofs to produce councilkey-os-*.iso with both BIOS and UEFI boot

**Flash to USB with persistence:**
```bash
# Find your USB
lsblk
# CAREFUL: replace /dev/sdX with your USB (e.g., /dev/sdb, NOT /dev/sda)
sudo dd if=output/councilkey-os-1.0-noble-amd64-live.iso of=/dev/sdX bs=4M status=progress && sync

# Create persistence partition (optional but recommended)
# Boot once into live, then or use gparted:
sudo parted /dev/sdX
# mkpart primary ext4 8GB 100%
# Then on that partition:
sudo mkfs.ext4 -L casper-rw /dev/sdX3
# For encryption (recommended):
sudo cryptsetup luksFormat /dev/sdX3
sudo cryptsetup open /dev/sdX3 casper-rw-crypt
sudo mkfs.ext4 -L casper-rw /dev/mapper/casper-rw-crypt

# Edit grub to add persistent flag: boot=casper persistent
```

**Boot:**
- Plug USB, hit Esc/F12/Del to open boot menu, pick USB
- Should boot to CouncilKey-Os desktop / TUI login
- Login: council / council (or openclaw for agent user)
- Open terminal: council status
- Browser: https://council.local:8443 (dashboard)

---

## Immutable Bootc - Fedora (Advanced, 2 hours, most secure)

Based on Tank-OS - best for enterprise, A/B rollback, cannot brick.

**Build host:** Fedora 44+ or Ubuntu with Podman, 50GB, podman installed.

**Setup:**
```bash
sudo dnf install podman make git qemu-kvm qemu-img -y  # Fedora
# or Ubuntu: sudo apt install podman make git qemu-kvm qemu-utils -y

git clone https://github.com/Nikhil009988/CouncilKey-Os
cd CouncilKey-Os
# Config for bootc-image-builder
cp builder/bootc/config.toml.example builder/bootc/config.toml
# Edit config.toml to inject your SSH public key for VM test
vim builder/bootc/config.toml
```

**Build:**
```bash
chmod +x scripts/build-bootc.sh
./scripts/build-bootc.sh

# Steps inside:
# 1. podman build -t localhost/councilkey-os:latest -f builder/bootc/Containerfile builder/bootc/
#    - Base: quay.io/fedora/fedora-bootc:44
#    - Installs: podman, python3, nodejs 22, cloud-init, openssh-server, qemu-guest-agent, tailscale
#    - Creates users council(1000), hermes(1001), openclaw(1002), agent0(1003) + linger + subuid
#    - Copies rootfs-overlay/ with Quadlet units
# 2. Build QCOW2
#    mkdir -p output/bootc
#    podman run --rm --privileged \
#      -v ./output/bootc:/output \
#      -v ./builder/bootc/config.toml:/config.toml:ro \
#      -v /var/lib/containers/storage:/var/lib/containers/storage \
#      quay.io/centos-bootc/bootc-image-builder:latest \
#      localhost/councilkey-os:latest --output /output/ --local --type qcow2 --target-arch amd64 --rootfs xfs --config /config.toml
# Output: output/bootc/qcow2/disk.qcow2
# 3. Build ISO and RAW optionally
#    --type iso -> for installer
#    --type raw -> for direct USB flash (like Reefy)
```

**Test in VM:**
```bash
./scripts/reefy-vm.sh # or manual qemu:
qemu-system-x86_64 \
  -M virt,highmem=on -accel kvm -cpu host -smp 4 -m 4096 \
  -drive file=output/bootc/qcow2/disk.qcow2,format=qcow2,if=virtio \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -nographic

# In another terminal
ssh -p 2222 council@localhost
# Inside VM
podman ps  # should show 4 containers: hermes, openclaw, agent-zero, council-core
council status
journalctl -u council-core -f
```

**Flash RAW to USB:**
```bash
# Build RAW type
podman run ... --type raw ...

# Flash to USB (RAW is like Reefy)
sudo dd if=output/bootc/raw/disk.raw of=/dev/sdX bs=4M status=progress && sync
# Or use Balena Etcher tool (cross-platform GUI)

# Boot physical hardware: disable Secure Boot in BIOS if needed
# Device appears in dashboard after online
```

**Upgrade running VM/device:**
```bash
# Inside VM/device
sudo bootc status
sudo bootc switch --apply quay.io/your-org/councilkey-os:latest
# Reboots to new version atomically, rollback on failure
sudo bootc rollback  # if needed
```

---

## Choosing Profile

| Need | Recommended Profile |
|------|---------------------|
| Test in 5 min on friend's PC without reboot | Portable USB |
| Boot any PC from pendrive, full desktop, persistence | Live ISO (Ubuntu) |
| Enterprise, fleet, 15-sec boot, cannot brick, secure | Immutable Bootc (Fedora) |
| Raspberry Pi / ARM64 | Bootc with --target-arch arm64 or Live ISO arm64 |

---

## CouncilKey-Os CLI After Boot

```bash
council ask "What is quantum computing? Debate among yourselves"
# -> Hermes provides memory/context, OpenClaw provides web search, Agent0 writes demo code, vote

council status
council logs --agent hermes -f
council shell openclaw # exec into container
council secrets add anthropic_api_key # prompts secure input
council dashboard # opens https://localhost:8443
council journal # git log of council decisions
```

---

## Troubleshooting

**Portable:**
- exFAT symlink error -> script uses cp -rL automatically, if manual need to resolve
- Node binary corrupted -> delete bin/linux/* and re-run setup.sh

**Live ISO:**
- Black screen on boot -> try safe graphics mode: delete quiet splash in grub, add nomodeset
- No WiFi -> chroot needs linux-firmware + wpasupplicant + network-manager; add your specific driver firmware
- Persistence not working -> ensure boot params include `persistent` and partition label is `casper-rw` or `writable`

**Bootc:**
- bootc-image-builder permission denied -> need --privileged and rootful podman machine on macOS
- QCOW2 SSH not reachable -> check port 2222 not used, lsof -ti:2222 | xargs kill
- Pulling 3.5GB openclaw image times out on boot -> inside VM: podman pull ghcr.io/openclaw/openclaw:latest manually, then systemctl --user restart openclaw.service (from tank-os docs)

---

## Next: See council/ directory for orchestrator code.
