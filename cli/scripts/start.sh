#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/.autofyn"

HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)}"
export HOST_IP
echo "[autofyn] Host IP: ${HOST_IP:-not detected}"

# Generate internal secrets if not already set by the user
if [ -z "${AGENT_INTERNAL_SECRET:-}" ]; then
    AGENT_INTERNAL_SECRET="$(openssl rand -hex 32)"
    export AGENT_INTERNAL_SECRET
fi

if [ -z "${SANDBOX_INTERNAL_SECRET:-}" ]; then
    SANDBOX_INTERNAL_SECRET="$(openssl rand -hex 32)"
    export SANDBOX_INTERNAL_SECRET
fi

# Only tear down if containers are already running
if docker compose ps -q 2>/dev/null | grep -q .; then
    docker compose down --remove-orphans 2>/dev/null || true
fi

# AF_FORCE_BUILD=1 → always build locally (autofyn start --build)
# Otherwise try pulling pre-built images; fall back to local build
if [ "${AF_FORCE_BUILD:-}" = "1" ]; then
    echo "[autofyn] Building images locally (--build)"
    docker compose up -d --build "$@"
elif docker compose pull 2>/dev/null; then
    echo "[autofyn] Using pre-built images"
    docker compose up -d "$@"
else
    echo "[autofyn] Pre-built images not available, building locally"
    docker compose up -d --build "$@"
fi
