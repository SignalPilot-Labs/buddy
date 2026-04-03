#!/bin/bash
set -e

API_PORT="${API_PORT:-3401}"
UI_PORT="${UI_PORT:-3400}"
API_KEY_FILE="/data/api.key"

# ── Resolve API key (single source of truth) ──────────────────────────────
# Priority: env var > persisted file > generate new
if [ -z "$DASHBOARD_API_KEY" ]; then
    if [ -f "$API_KEY_FILE" ]; then
        DASHBOARD_API_KEY="$(cat "$API_KEY_FILE")"
    else
        DASHBOARD_API_KEY="$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 24)"
        echo -n "$DASHBOARD_API_KEY" > "$API_KEY_FILE"
        chmod 600 "$API_KEY_FILE"
        echo "[dashboard] Generated new API key (persisted in volume)"
    fi
fi

export DASHBOARD_API_KEY

# ── Resolve host LAN IP for QR code mobile access ────────────────────────
# Priority: HOST_IP env var > query host via host.docker.internal
if [ -z "$HOST_IP" ]; then
    HOST_IP="$(getent hosts host.docker.internal 2>/dev/null | awk '{print $1}')" || true
fi
export HOST_IP

# Inject runtime config into frontend (NEXT_PUBLIC_ only works at build time)
cat > /app/frontend/public/config.js <<JSEOF
window.__BUDDY_API_KEY__="${DASHBOARD_API_KEY}";
JSEOF

echo "[dashboard] API key: $DASHBOARD_API_KEY"
echo "[dashboard] Host IP: ${HOST_IP:-unknown}"

# Start FastAPI backend
uvicorn backend.app:app --host 0.0.0.0 --port "$API_PORT" &
FASTAPI_PID=$!

# Wait for FastAPI to be ready
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${API_PORT}/api/settings/status" \
         -H "X-API-Key: ${DASHBOARD_API_KEY}" > /dev/null 2>&1; then
        echo "[dashboard] FastAPI backend ready on :${API_PORT}"
        break
    fi
    sleep 0.5
done

# Start Next.js frontend
cd /app/frontend
API_URL="http://localhost:${API_PORT}" npx next start --port "$UI_PORT" &
NEXT_PID=$!

echo "[dashboard] Next.js frontend ready on :${UI_PORT}"

# Wait for either process to exit
wait -n $FASTAPI_PID $NEXT_PID
