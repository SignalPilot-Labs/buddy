#!/bin/bash
# Build the ext4 rootfs image for Firecracker microVMs
#
# This runs inside the Dockerfile.rootfs builder container.
# Output: /output/sandbox-rootfs.ext4

set -euo pipefail

ROOTFS_SIZE_MB=1024
OUTPUT_PATH="/output/sandbox-rootfs.ext4"

echo "Building sandbox rootfs (${ROOTFS_SIZE_MB}MB)..."

# Create empty ext4 image
dd if=/dev/zero of="${OUTPUT_PATH}" bs=1M count="${ROOTFS_SIZE_MB}"
mkfs.ext4 "${OUTPUT_PATH}"

# Mount and copy filesystem
MOUNT_DIR=$(mktemp -d)
mount "${OUTPUT_PATH}" "${MOUNT_DIR}"

# Copy the essential filesystem from this container
for dir in bin etc lib lib64 opt root sbin usr var; do
    if [ -d "/${dir}" ]; then
        cp -a "/${dir}" "${MOUNT_DIR}/"
    fi
done

# Create required directories
mkdir -p "${MOUNT_DIR}"/{dev,proc,sys,tmp,run}
mkdir -p "${MOUNT_DIR}/tmp/output"

# Create init script that starts the sandbox agent
cat > "${MOUNT_DIR}/etc/init.d/rcS" << 'INIT'
#!/bin/sh
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev

# Start sandbox agent
/usr/bin/python3 /opt/signalpilot/sandbox_agent.py &

# Keep the VM alive
exec /bin/sh
INIT
chmod +x "${MOUNT_DIR}/etc/init.d/rcS"

# Create inittab
cat > "${MOUNT_DIR}/etc/inittab" << 'INITTAB'
::sysinit:/etc/init.d/rcS
::respawn:-/bin/sh
::ctrlaltdel:/sbin/reboot
INITTAB

umount "${MOUNT_DIR}"
rmdir "${MOUNT_DIR}"

echo "Rootfs built: ${OUTPUT_PATH} ($(du -h ${OUTPUT_PATH} | cut -f1))"
