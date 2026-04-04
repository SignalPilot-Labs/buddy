#!/bin/bash
set -e

API_PORT="${API_PORT:-3401}"
UI_PORT="${UI_PORT:-3400}"
API_KEY_FILE="/data/api.key"

# ── Generate API key if missing (persists in buddy-keys volume) ───────────
if [ ! -f "$API_KEY_FILE" ]; then
    head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 24 > "$API_KEY_FILE"
    chmod 600 "$API_KEY_FILE"
    echo "[dashboard] Generated new API key"
fi

API_KEY="$(cat "$API_KEY_FILE")"

# Inject into frontend runtime config (NEXT_PUBLIC_ only works at build time)
echo "window.__BUDDY_API_KEY__=\"${API_KEY}\";" > /app/frontend/public/config.js

echo "[dashboard] API key: ${API_KEY}"
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

# ── Start Next.js frontend ───────────────────────────────────────────────
cd /app/frontend
API_URL="http://localhost:${API_PORT}" npx next start --port "$UI_PORT" &
NEXT_PID=$!

echo "[dashboard] Next.js frontend ready on :${UI_PORT}"

wait -n $FASTAPI_PID $NEXT_PID
