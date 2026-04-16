#!/bin/bash
set -e

API_PORT="${API_PORT:-3401}"
UI_PORT="${UI_PORT:-3400}"
API_KEY_FILE="/data/api.key"

# ── Generate API key if missing (persists in autofyn-keys volume) ───────────
if [ ! -f "$API_KEY_FILE" ]; then
    head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 24 > "$API_KEY_FILE"
    chmod 600 "$API_KEY_FILE"
    echo "[dashboard] Generated new API key"
fi

API_KEY="$(cat "$API_KEY_FILE")"

export DASHBOARD_API_KEY="$API_KEY"

echo "[dashboard] API key loaded (${API_KEY:0:4}****)"
echo "[dashboard] Host IP: ${HOST_IP:-not set}"

# ── Start FastAPI backend ─────────────────────────────────────────────────
uvicorn backend.app:app --host 0.0.0.0 --port "$API_PORT" &
FASTAPI_PID=$!

for i in $(seq 1 30); do
    if curl -sf "http://localhost:${API_PORT}/api/settings/status" \
         -H "X-API-Key: ${API_KEY}" > /dev/null 2>&1; then
        echo "[dashboard] FastAPI backend ready on :${API_PORT}"
        break
    fi
    sleep 0.5
done

# ── Start Next.js frontend (standalone server) ───────────────────────────
cd /app/frontend
export API_URL="http://localhost:${API_PORT}"
API_URL="http://localhost:${API_PORT}" PORT="$UI_PORT" HOSTNAME="0.0.0.0" node server.js &
NEXT_PID=$!

echo "[dashboard] Next.js frontend ready on :${UI_PORT}"

wait -n $FASTAPI_PID $NEXT_PID
