#!/usr/bin/env bash
# Installs gVisor (runsc) and registers it as a Docker runtime.
#
#   sudo bash scripts/setup-gvisor.sh
#
# Note: this restarts the Docker daemon. The ollama container has
# `restart: unless-stopped` and will come back up on its own.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "This script must run as root: sudo bash scripts/setup-gvisor.sh" >&2
    exit 1
fi

ARCH=$(uname -m)
URL="https://storage.googleapis.com/gvisor/releases/release/latest/${ARCH}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"

echo "Downloading runsc for ${ARCH}..."
wget -q "${URL}/runsc" "${URL}/runsc.sha512" \
    "${URL}/containerd-shim-runsc-v1" "${URL}/containerd-shim-runsc-v1.sha512"
sha512sum -c runsc.sha512
sha512sum -c containerd-shim-runsc-v1.sha512
chmod a+rx runsc containerd-shim-runsc-v1
mv runsc containerd-shim-runsc-v1 /usr/local/bin/

echo "Registering runsc runtime in /etc/docker/daemon.json (existing runtimes are preserved)..."
/usr/local/bin/runsc install

echo "Restarting Docker..."
systemctl restart docker

echo
echo "Done. Verify with:"
echo "  docker run --rm --runtime=runsc python:3.13-slim dmesg | head -1"
echo "(the first line should mention gVisor)"
