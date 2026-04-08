#!/bin/bash
set -e

# Install QEMU if not present
apt-get update && apt-get install -y qemu-system-x86 2>/dev/null || true

# Boot Alpine ISO in background with telnet serial console
qemu-system-x86_64 \
    -m 512 \
    -cdrom /app/alpine.iso \
    -boot d \
    -nographic \
    -serial telnet:127.0.0.1:6665,server,nowait \
    -display none \
    -no-reboot &

# Wait for boot
echo "Waiting for QEMU to boot..."
sleep 30

echo "QEMU started. Telnet should be available on port 6665."
