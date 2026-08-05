#!/usr/bin/env bash
set -euo pipefail
CODENAME="${1:-noble}"
ARCH="${2:-amd64}"
OUT="${3:-output}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$OUT/image/casper" "$OUT/image/isolinux" "$OUT/image/pool/main"
sudo debootstrap --arch="$ARCH" "$CODENAME" "$ROOT/output/chroot" http://archive.ubuntu.com/ubuntu/ || true
sudo cp "$ROOT/builder/live/council-storage-setup.sh" "$ROOT/output/chroot/usr/local/bin/council-storage-setup.sh"
sudo chmod +x "$ROOT/output/chroot/usr/local/bin/council-storage-setup.sh"
sudo mksquashfs "$ROOT/output/chroot" "$OUT/image/casper/filesystem.squashfs" -comp xz -e boot || true
echo "Live ISO skeleton at $OUT/image/casper/filesystem.squashfs"
