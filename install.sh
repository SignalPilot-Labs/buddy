#!/usr/bin/env bash
set -euo pipefail

BUDDY_HOME="$HOME/.buddy"

echo "[install] Installing Buddy to ${BUDDY_HOME}/"

# Copy repo to ~/.buddy/ (overwrite existing)
if [ -d "$BUDDY_HOME" ]; then
    # Preserve config and Docker volumes
    echo "[install] Updating existing installation"
    rsync -a --exclude='cli.toml' --exclude='node_modules' --exclude='.next' --exclude='__pycache__' \
        ./ "$BUDDY_HOME/"
else
    mkdir -p "$BUDDY_HOME"
    cp -R . "$BUDDY_HOME/"
fi

# Install CLI
pip install -e "$BUDDY_HOME/cli/" --quiet

echo ""
echo "[install] Done. Run 'buddy start' to launch."
