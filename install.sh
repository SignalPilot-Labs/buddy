#!/usr/bin/env bash
set -euo pipefail

BUDDY_HOME="$HOME/.buddy"

echo "[install] Installing Buddy to ${BUDDY_HOME}/"

# Copy repo to ~/.buddy/
if [ -d "$BUDDY_HOME" ]; then
    echo "[install] Updating existing installation"
    # Preserve config.json if it exists
    CONFIG_BAK=""
    if [ -f "$BUDDY_HOME/config.json" ]; then
        CONFIG_BAK="$(mktemp)"
        cp "$BUDDY_HOME/config.json" "$CONFIG_BAK"
    fi
    rm -rf "$BUDDY_HOME"
    mkdir -p "$BUDDY_HOME"
    cp -R . "$BUDDY_HOME/"
    # Restore config
    if [ -n "$CONFIG_BAK" ]; then
        mv "$CONFIG_BAK" "$BUDDY_HOME/config.json"
    fi
else
    mkdir -p "$BUDDY_HOME"
    cp -R . "$BUDDY_HOME/"
fi

# Install CLI
pip install -e "$BUDDY_HOME/cli/" --quiet

# Build Docker images and start services
echo "[install] Building Docker images..."
bash "$BUDDY_HOME/cli/scripts/build.sh"
echo "[install] Starting services..."
bash "$BUDDY_HOME/cli/scripts/up.sh"

echo ""
echo "[install] Done. Run 'buddy settings set' to configure credentials."
