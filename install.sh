#!/usr/bin/env bash
set -euo pipefail

AUTOFYN_HOME="$HOME/.autofyn"

echo "[install] Installing AutoFyn to ${AUTOFYN_HOME}/"

# Copy repo to ~/.autofyn/
if [ -d "$AUTOFYN_HOME" ]; then
    echo "[install] Updating existing installation"
    # Preserve config.json if it exists
    CONFIG_BAK=""
    if [ -f "$AUTOFYN_HOME/config.json" ]; then
        CONFIG_BAK="$(mktemp)"
        cp "$AUTOFYN_HOME/config.json" "$CONFIG_BAK"
    fi
    rm -rf "$AUTOFYN_HOME"
    mkdir -p "$AUTOFYN_HOME"
    cp -R . "$AUTOFYN_HOME/"
    # Restore config
    if [ -n "$CONFIG_BAK" ]; then
        mv "$CONFIG_BAK" "$AUTOFYN_HOME/config.json"
    fi
else
    mkdir -p "$AUTOFYN_HOME"
    cp -R . "$AUTOFYN_HOME/"
fi

# Install CLI
pip install -e "$AUTOFYN_HOME/cli/" --quiet

# Pull pre-built Docker images (fall back to local build)
export AUTOFYN_IMAGE_TAG="main"
echo "[install] Pulling Docker images..."
if ! (cd "$AUTOFYN_HOME" && docker compose pull 2>/dev/null); then
    echo "[install] Pre-built images not available, building locally..."
    bash "$AUTOFYN_HOME/cli/scripts/build.sh"
fi

echo ""
echo "[install] Done. Run 'autofyn start' to launch services."
