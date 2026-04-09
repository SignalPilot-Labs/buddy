#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/.autofyn"

HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)}"
export HOST_IP
echo "[autofyn] Host IP: ${HOST_IP:-not detected}"

# Generate internal secret if not already set by the user
if [ -z "${AGENT_INTERNAL_SECRET:-}" ]; then
    AGENT_INTERNAL_SECRET="$(openssl rand -hex 32)"
    export AGENT_INTERNAL_SECRET
fi

docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d "$@"
