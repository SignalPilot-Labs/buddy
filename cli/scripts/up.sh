#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/.buddy"
if [ -z "${HOST_IP:-}" ]; then
    HOST_IP="$(ipconfig getifaddr en0 2>/dev/null)" \
      || HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')" \
      || HOST_IP=""
fi
export HOST_IP
echo "[buddy] Host IP: ${HOST_IP:-not detected}"
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d "$@"
