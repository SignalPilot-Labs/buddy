#!/bin/bash
# SignalPilot Firecracker Setup — macOS
#
# Checks prerequisites for running Firecracker inside Docker on macOS.
# macOS support depends on Docker Desktop's nested virtualization
# which is available on Apple Silicon (M1+) with recent Docker Desktop versions.
#
# Usage:
#   chmod +x setup-macos.sh && ./setup-macos.sh

set -euo pipefail

echo ""
echo "========================================"
echo "  SignalPilot Firecracker Setup (macOS)  "
echo "========================================"
echo ""

# ─── Step 1: Check macOS version ────────────────────────────────────────────

MACOS_VERSION=$(sw_vers -productVersion)
MACOS_MAJOR=$(echo "$MACOS_VERSION" | cut -d. -f1)
echo "[OK] macOS ${MACOS_VERSION}"

if [ "$MACOS_MAJOR" -lt 13 ]; then
    echo "[FAIL] macOS 13 (Ventura) or later required for nested virtualization."
    exit 1
fi

# ─── Step 2: Check CPU architecture ─────────────────────────────────────────

ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    echo "[OK] Apple Silicon ($ARCH) — nested virtualization supported"
elif [ "$ARCH" = "x86_64" ]; then
    echo "[WARN] Intel Mac ($ARCH) — nested virtualization may work but is less tested"
    echo "       Intel Macs are EOL. Consider container fallback mode."
else
    echo "[FAIL] Unknown architecture: $ARCH"
    exit 1
fi

# ─── Step 3: Check Docker Desktop ───────────────────────────────────────────

if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo "[OK] ${DOCKER_VERSION}"
else
    echo "[FAIL] Docker not found. Install Docker Desktop from docker.com"
    exit 1
fi

# ─── Step 4: Check for KVM inside Docker ────────────────────────────────────

echo "[...] Checking /dev/kvm inside Docker..."
KVM_CHECK=$(docker run --rm --device /dev/kvm alpine ls /dev/kvm 2>&1 || true)

if echo "$KVM_CHECK" | grep -q "/dev/kvm"; then
    echo "[OK] /dev/kvm available inside Docker — Firecracker ready!"
else
    echo "[WARN] /dev/kvm not available inside Docker."
    echo ""
    echo "  To enable on Apple Silicon:"
    echo "    1. Open Docker Desktop → Settings → General"
    echo "    2. Enable 'Use Virtualization framework'"
    echo "    3. Enable 'Use Rosetta for x86_64/amd64 emulation' (if needed)"
    echo "    4. Settings → Resources → Advanced"
    echo "    5. Check for nested virtualization option"
    echo "    6. Restart Docker Desktop"
    echo ""
    echo "  If nested virtualization is not available in your Docker Desktop version:"
    echo "    SignalPilot will automatically fall back to container sandbox mode."
    echo "    Run: sp serve --sandbox-mode=container"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  Setup Summary"
echo "========================================"
echo ""

if echo "$KVM_CHECK" | grep -q "/dev/kvm"; then
    echo "Ready! Run:"
    echo "  docker run --device /dev/kvm signalpilot-sandbox"
else
    echo "Firecracker not available. Options:"
    echo "  1. Update Docker Desktop and enable nested virtualization"
    echo "  2. Use container sandbox mode: sp serve --sandbox-mode=container"
    echo "  3. Use SignalPilot Cloud: sp login"
fi

echo ""
