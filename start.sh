#!/usr/bin/env bash
set -euo pipefail

# ─── Pinned versions (source of truth) ──────────────────────────────────────
PYTHON_VERSION=3.12
NODE_VERSION=22
GVISOR_VERSION=20260323.0
FIRECRACKER_VERSION=1.10.1
DOCKER_CLI_VERSION=27.5.1
POSTGRES_VERSION=16
UBUNTU_VERSION=22.04

# ─── Auto-detect host LAN IP for mobile QR code access ─────────────────────
if [ -z "${HOST_IP:-}" ]; then
    HOST_IP="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)"
    export HOST_IP
fi
echo "[build] Host IP: ${HOST_IP:-not detected}"

# ─── Build then run ─────────────────────────────────────────────────────────
docker compose build \
    --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
    --build-arg NODE_VERSION="$NODE_VERSION" \
    --build-arg GVISOR_VERSION="$GVISOR_VERSION" \
    --build-arg FIRECRACKER_VERSION="$FIRECRACKER_VERSION" \
    --build-arg DOCKER_CLI_VERSION="$DOCKER_CLI_VERSION" \
    --build-arg POSTGRES_VERSION="$POSTGRES_VERSION" \
    --build-arg UBUNTU_VERSION="$UBUNTU_VERSION"

docker compose up "$@"
