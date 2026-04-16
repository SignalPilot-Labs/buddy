#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/.autofyn"

HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)}"
export HOST_IP
echo "[autofyn] Host IP: ${HOST_IP:-not detected}"

# Write AGENT_INTERNAL_SECRET to .env if not already present.
# Compose auto-loads .env from cwd ($HOME/.autofyn) — no need to export.
ENV_FILE="$HOME/.autofyn/.env"
if [ ! -f "$ENV_FILE" ] || ! grep -q "^AGENT_INTERNAL_SECRET=" "$ENV_FILE"; then
    echo "AGENT_INTERNAL_SECRET=$(openssl rand -hex 32)" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "[autofyn] Generated new AGENT_INTERNAL_SECRET and wrote to ${ENV_FILE}"
fi
if ! grep -q "^SANDBOX_INTERNAL_SECRET=" "$ENV_FILE"; then
    echo "SANDBOX_INTERNAL_SECRET=$(openssl rand -hex 32)" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "[autofyn] Generated new SANDBOX_INTERNAL_SECRET and wrote to ${ENV_FILE}"
fi

docker compose --env-file "$ENV_FILE" down --remove-orphans 2>/dev/null || true
docker compose --env-file "$ENV_FILE" up -d "$@"
