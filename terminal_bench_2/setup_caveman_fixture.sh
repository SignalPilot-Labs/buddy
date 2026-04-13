#!/usr/bin/env bash
# Creates the caveman plugin fixture files expected by load_caveman_skill().
# Idempotent — safe to run multiple times.
set -euo pipefail

PLUGINS_DIR="${HOME}/.claude/plugins"
PLUGIN_INSTALL_DIR="${PLUGINS_DIR}/caveman-plugin"
SKILL_DIR="${PLUGIN_INSTALL_DIR}/caveman"
SKILL_FILE="${SKILL_DIR}/SKILL.md"
INSTALLED_PLUGINS_JSON="${PLUGINS_DIR}/installed_plugins.json"

echo "Setting up caveman plugin fixture..."

mkdir -p "${SKILL_DIR}"

cat > "${SKILL_FILE}" << 'EOF'
# Caveman SKILL.md placeholder — not available in this environment.
EOF

cat > "${INSTALLED_PLUGINS_JSON}" << EOF
{
  "plugins": {
    "caveman@caveman": [
      {
        "installPath": "${PLUGIN_INSTALL_DIR}"
      }
    ]
  }
}
EOF

echo "Caveman fixture ready:"
echo "  plugins json : ${INSTALLED_PLUGINS_JSON}"
echo "  skill file   : ${SKILL_FILE}"
