#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/.autofyn"

HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)}"
export HOST_IP
echo "[autofyn] Host IP: ${HOST_IP:-not detected}"

# Read image tag persisted by `autofyn update`
TAG_FILE="$HOME/.autofyn/.image-tag"
if [ -z "${AF_IMAGE_TAG:-}" ] && [ -f "$TAG_FILE" ]; then
    AF_IMAGE_TAG="$(cat "$TAG_FILE" | tr -d '[:space:]')"
fi
if [ -z "${AF_IMAGE_TAG:-}" ]; then
    echo "[autofyn] ERROR: No image tag found. Run 'autofyn update' first." >&2
    exit 1
fi
export AF_IMAGE_TAG
echo "[autofyn] Image tag: ${AF_IMAGE_TAG}"

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

docker compose up -d "$@"
