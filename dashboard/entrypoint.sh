#!/bin/bash
set -e

API_PORT="${API_PORT:-3401}"
UI_PORT="${UI_PORT:-3400}"

# Start FastAPI backend
uvicorn backend.app:app --host 0.0.0.0 --port "$API_PORT" &
FASTAPI_PID=$!

# Wait for FastAPI to be ready
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${API_PORT}/api/runs" > /dev/null 2>&1; then
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
