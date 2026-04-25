#!/usr/bin/env bash
set -euo pipefail

AUTOFYN_HOME="$HOME/.autofyn"

echo "[uninstall] Stopping AutoFyn services..."
cd "$AUTOFYN_HOME" 2>/dev/null && docker compose down --remove-orphans --volumes 2>/dev/null || true

echo "[uninstall] Removing Docker images..."
docker images --filter "reference=autofyn-*" -q | xargs docker rmi -f 2>/dev/null || true

echo "[uninstall] Uninstalling CLI..."
pip uninstall autofyn-cli -y 2>/dev/null || true

echo "[uninstall] Removing $AUTOFYN_HOME..."
rm -rf "$AUTOFYN_HOME"

echo ""
echo "[uninstall] Done. AutoFyn has been removed."
