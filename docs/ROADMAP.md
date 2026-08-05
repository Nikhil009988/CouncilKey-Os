# Roadmap

## What we have now (tried and working)

✅ Portable council in /tmp/council-usb-demo - mocked 3 agents, voting, journal git log
✅ Orchestrator main.py works: status, ask, dashboard, journal
✅ Build scripts: build-portable.sh, build-live-iso.sh (Ubuntu from scratch), build-bootc.sh (Fedora bootc like Tank-OS)
✅ Surveyed related projects: exFAT symlinks, bootc Quadlet, Buildroot, casper persistence
✅ Architecture: 3 partitions, LUKS encrypted persistence, council voting

## What to try next on real USB

### Step 1: Get 64GB USB, format exFAT
```
sudo mkfs.exfat -n COUNCIL /dev/sdX1
sudo mount /dev/sdX1 /mnt/council
./scripts/build-portable.sh /mnt/council
# If nodejs.org fails, manually download node and place in bin/linux/
# Then: bash /mnt/council/start.sh
# council ask "why council better than single?"
```

### Step 2: Build Live ISO (needs 50GB disk, Ubuntu host)
```
sudo ./scripts/build-live-iso.sh noble amd64
# Output iso in output/
# dd to USB:
sudo dd if=output/councilkey-os-1.0-noble-amd64-live.iso of=/dev/sdX bs=4M status=progress
# Create persistence partition:
sudo parted /dev/sdX -- mkpart primary ext4 8GiB 100%
sudo mkfs.ext4 -L casper-rw /dev/sdX3
# Or encrypted:
sudo cryptsetup luksFormat /dev/sdX3
sudo cryptsetup open /dev/sdX3 casper-rw-crypt
sudo mkfs.ext4 -L casper-rw /dev/mapper/casper-rw-crypt
# Boot: disable secure boot, pick USB, login council/council
```

### Step 3: Bootc RAW (most secure, like Reefy & Tank-OS)
```
podman machine init --rootful # macOS only
podman build -t localhost/councilkey-os:latest -f builder/bootc/Containerfile builder/bootc/
mkdir -p output/bootc
podman run --rm --privileged -v ./output/bootc:/output -v ./builder/bootc/config.toml:/config.toml:ro -v /var/lib/containers/storage:/var/lib/containers/storage quay.io/centos-bootc/bootc-image-builder:latest localhost/councilkey-os:latest --output /output --local --type raw --target-arch amd64 --rootfs xfs --config /config.toml
# Flash raw:
sudo dd if=output/bootc/raw/disk.raw of=/dev/sdX bs=4M status=progress
# Or Balena Etcher
```

## Integration TODO for real 3 agents

Current orchestrator uses mock responses when ports closed. To make real:

- **OpenClaw real**: Install via npm, run `openclaw gateway start` gives HTTP API at 18789. Need to implement POST /api/message forwarding in AgentAdapter.ask()
- **Hermes real**: After cloning hermes-agent, `hermes gateway setup` creates config, `hermes gateway start` gives API at 18790. Implement tool.
- **Agent-Zero real**: `python run_ui.py --port 50001` gives WebUI + API at /api/message. Implement forwarding.

Then voting becomes real - 3 LLMs debating.

## Boot optimization ideas from Reefy scan

Reefy achieves 15s boot by:
- Custom kernel 6.18.40 with only needed drivers (kernel-config file from board/reefy)
- systemd-analyze critical-chain to remove slow units
- No package manager on device
- Squashfs + overlay

We can apply same: start from Reefy_defconfig, add council packages, reuse their post_build.sh.

## Other ideas from scans

- Use Tailscale for remote access to council like Reefy (BR2_PACKAGE_TAILSCALE_REEFY)
- Use MQTT for inter-agent pub/sub (Reefy does)
- Use Nous Portal for single subscription covering 300+ models (Hermes new feature)
- Use OpenShell for secure container exec (Tank-OS includes nvidia openshell RPMs)
- Git-versioned journal like Contextium pattern (our implementation already does git commit in journal/)

## Pendrive hardware recommendations

- Minimum 32GB, recommended 64-128GB USB 3.0+
- USB3 is 3x faster than USB2 even in USB2 port (from forum scan)
- For RAW bootc image, need >=16GB
- For portable exFAT, 16GB enough but 64GB allows caching models via Ollama
- For local LLM fully offline, need 8GB+ RAM host + 16GB VRAM if want GPU, or run small models like qwen2.5:7b
