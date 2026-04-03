#!/usr/bin/env bash
set -euo pipefail

# ─── Pinned versions (source of truth) ──────────────────────────────────────
PYTHON_VERSION=3.12
NODE_VERSION=22
GVISOR_VERSION=20260323.0
FIRECRACKER_VERSION=1.10.1

# ─── Build ───────────────────────────────────────────────────────────────────
docker compose build \
    --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
    --build-arg NODE_VERSION="$NODE_VERSION" \
    --build-arg GVISOR_VERSION="$GVISOR_VERSION" \
    --build-arg FIRECRACKER_VERSION="$FIRECRACKER_VERSION" \
    "$@"
