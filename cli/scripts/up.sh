#!/usr/bin/env bash
set -euo pipefail
if ! docker info >/dev/null 2>&1; then
    echo "[error] Docker daemon is not running. Start Docker and try again." >&2
    exit 1
fi
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
echo "[buddy] Waiting for dashboard to be ready..."
_timeout=60
_elapsed=0
while [ "$_elapsed" -lt "$_timeout" ]; do
    if curl -sf http://localhost:3401/api/health >/dev/null 2>&1; then
        printf "\n"
        echo "[ok] Dashboard is ready"
        exit 0
    fi
    printf "."
    sleep 1
    _elapsed=$((_elapsed + 1))
done
printf "\n"
echo "[error] Dashboard did not become ready within ${_timeout}s — check: docker compose logs" >&2
exit 1
