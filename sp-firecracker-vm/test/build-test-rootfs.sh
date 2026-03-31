#!/bin/bash
# Builds the rootfs directory tree during docker build.
# The ext4 image is created at runtime (needs privileges).
set -euo pipefail

ROOTFS_DIR="/opt/rootfs-tree"

echo "=== Building rootfs directory tree ==="

mkdir -p "${ROOTFS_DIR}"/{bin,sbin,etc,proc,sys,dev,tmp,usr/bin,usr/lib,lib,lib64,opt,root,run,var}
mkdir -p "${ROOTFS_DIR}/tmp/output"
mkdir -p "${ROOTFS_DIR}/lib/x86_64-linux-gnu"
mkdir -p "${ROOTFS_DIR}/usr/lib/x86_64-linux-gnu"

# Install busybox for minimal userland
apt-get update && apt-get install -y --no-install-recommends busybox-static
cp /bin/busybox "${ROOTFS_DIR}/bin/busybox"
# Create symlinks manually (can't chroot without mount)
for cmd in sh ls cat echo mkdir mount umount sleep poweroff reboot hostname uname; do
    ln -sf busybox "${ROOTFS_DIR}/bin/${cmd}"
done

# Copy Python
cp /usr/bin/python3 "${ROOTFS_DIR}/usr/bin/python3"
ln -sf python3 "${ROOTFS_DIR}/usr/bin/python"

# Copy Python shared libraries
for lib in $(ldd /usr/bin/python3 | grep -o '/[^ ]*'); do
    dir=$(dirname "$lib")
    mkdir -p "${ROOTFS_DIR}${dir}"
    cp -L "$lib" "${ROOTFS_DIR}${lib}" 2>/dev/null || true
done

# Copy dynamic linker
cp -L /lib64/ld-linux-x86-64.so.2 "${ROOTFS_DIR}/lib64/" 2>/dev/null || true
mkdir -p "${ROOTFS_DIR}/lib/x86_64-linux-gnu"
cp -L /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 "${ROOTFS_DIR}/lib/x86_64-linux-gnu/" 2>/dev/null || true

# Copy Python standard library
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
mkdir -p "${ROOTFS_DIR}/usr/lib/python${PYTHON_VERSION}"
cp -r "/usr/lib/python${PYTHON_VERSION}"/* "${ROOTFS_DIR}/usr/lib/python${PYTHON_VERSION}/" 2>/dev/null || true

# Copy additional shared libs
for lib in libpython libz libexpat libm libc libdl libutil libpthread librt libnsl libcrypt libresolv; do
    find /usr/lib /lib -name "${lib}*.so*" -exec sh -c 'mkdir -p /opt/rootfs-tree/$(dirname "$1") && cp -L "$1" /opt/rootfs-tree/"$1"' _ {} \; 2>/dev/null || true
done

# Create init script
cat > "${ROOTFS_DIR}/init" << 'INITSCRIPT'
#!/bin/sh
mount -t proc proc /proc 2>/dev/null
mount -t sysfs sysfs /sys 2>/dev/null
mount -t devtmpfs devtmpfs /dev 2>/dev/null

echo ""
echo "============================================"
echo "  SignalPilot Firecracker VM - BOOT SUCCESS"
echo "============================================"
echo ""
echo "Kernel: $(uname -r)"
echo "PID: $$"
echo ""

echo "Testing Python..."
/usr/bin/python3 -c "
import sys, json, os
result = {
    'status': 'ok',
    'python': sys.version.split()[0],
    'platform': sys.platform,
    'pid': os.getpid(),
    'message': 'Hello from inside a Firecracker microVM!'
}
print(json.dumps(result, indent=2))
" 2>&1 || echo "(Python unavailable - boot still succeeded)"

echo ""
echo "============================================"
echo "  VM READY - Firecracker is working!"
echo "============================================"
echo ""
sleep 3
echo "Shutting down..."
/bin/busybox poweroff -f
INITSCRIPT
chmod +x "${ROOTFS_DIR}/init"

# Minimal etc files
echo "root:x:0:0:root:/root:/bin/sh" > "${ROOTFS_DIR}/etc/passwd"
echo "root:x:0:" > "${ROOTFS_DIR}/etc/group"

# Cleanup build deps
apt-get remove -y busybox-static && apt-get autoremove -y 2>/dev/null || true
rm -rf /var/lib/apt/lists/*

echo "=== Rootfs tree built: $(du -sh ${ROOTFS_DIR} | cut -f1) ==="
