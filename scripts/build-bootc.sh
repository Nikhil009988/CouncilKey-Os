#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TYPE="${1:-qcow2}"
IMAGE="localhost/councilkey-os:latest"
mkdir -p "$ROOT/output/bootc"
podman build --platform linux/amd64 -t "$IMAGE" -f "$ROOT/builder/bootc/Containerfile" "$ROOT/builder/bootc" || true
if [ "$TYPE" = "qcow2" ] || [ "$TYPE" = "raw" ]; then
  podman run --rm --privileged \
    --security-opt label=type:unconfined_t \
    -v "$ROOT/output/bootc":/output \
    -v "$ROOT/builder/bootc/config.toml.example":/config.toml:ro \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    quay.io/centos-bootc/bootc-image-builder:latest \
    "$IMAGE" --output /output --local --type "$TYPE" --target-arch amd64 --rootfs xfs --config /config.toml || true
fi
echo "Bootc build output at $ROOT/output/bootc"
