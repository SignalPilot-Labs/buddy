#!/usr/bin/env bash
set -euo pipefail

AUTOFYN_HOME="$HOME/.autofyn"

echo "[install] Installing AutoFyn to ${AUTOFYN_HOME}/"

# Copy repo to ~/.autofyn/
if [ -d "$AUTOFYN_HOME" ]; then
    echo "[install] Updating existing installation"
    # Preserve config.json and .env if they exist
    CONFIG_BAK=""
    ENV_BAK=""
    if [ -f "$AUTOFYN_HOME/config.json" ]; then
        CONFIG_BAK="$(mktemp)"
        cp "$AUTOFYN_HOME/config.json" "$CONFIG_BAK"
    fi
    if [ -f "$AUTOFYN_HOME/.env" ]; then
        ENV_BAK="$(mktemp)"
        cp "$AUTOFYN_HOME/.env" "$ENV_BAK"
    fi
    rm -rf "$AUTOFYN_HOME"
    mkdir -p "$AUTOFYN_HOME"
    cp -R . "$AUTOFYN_HOME/"
    # Restore preserved files
    if [ -n "$CONFIG_BAK" ]; then
        mv "$CONFIG_BAK" "$AUTOFYN_HOME/config.json"
    fi
    if [ -n "$ENV_BAK" ]; then
        mv "$ENV_BAK" "$AUTOFYN_HOME/.env"
        chmod 600 "$AUTOFYN_HOME/.env"
    fi
else
    mkdir -p "$AUTOFYN_HOME"
    cp -R . "$AUTOFYN_HOME/"
fi

# Seed .env with a random AGENT_INTERNAL_SECRET on first install.
# up.sh also does this, so either can run first — both are idempotent.
ENV_FILE="$AUTOFYN_HOME/.env"
if [ ! -f "$ENV_FILE" ] || ! grep -q "^AGENT_INTERNAL_SECRET=" "$ENV_FILE"; then
    NEW_SECRET="$(openssl rand -hex 32)"
    echo "AGENT_INTERNAL_SECRET=${NEW_SECRET}" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "[install] Generated AGENT_INTERNAL_SECRET and wrote to ${ENV_FILE}"
fi

# Install CLI
pip install -e "$AUTOFYN_HOME/cli/" --quiet

# Build Docker images
echo "[install] Building Docker images..."
bash "$AUTOFYN_HOME/cli/scripts/build.sh"

echo ""
echo "[install] Done. Run 'autofyn start' to launch services."
