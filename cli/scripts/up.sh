#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/.autofyn"
HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)}"
export HOST_IP
echo "[autofyn] Host IP: ${HOST_IP:-not detected}"
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d "$@"
