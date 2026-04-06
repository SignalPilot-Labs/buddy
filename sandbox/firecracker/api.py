"""Firecracker infrastructure — socket API client and rootfs I/O."""

import http.client
import json
import logging
import os
import pathlib
import shutil
import socket
import subprocess
import time
import uuid

log = logging.getLogger("firecracker.api")

# ─── Paths ───────────────────────────────────────────────────────────────────

KERNEL_PATH = "/opt/autofyn/kernel/vmlinux.bin"
BASE_ROOTFS_PATH = "/opt/autofyn/rootfs/sandbox-rootfs.ext4"
OVERLAYS_DIR = "/opt/autofyn/overlays"
SOCKETS_DIR = "/opt/autofyn/sockets"
SNAPSHOT_DIR = "/opt/autofyn/snapshot"
SNAP_FILE = os.path.join(SNAPSHOT_DIR, "vm.snap")
MEM_FILE = os.path.join(SNAPSHOT_DIR, "vm.mem")


# ─── Unix socket HTTP client ────────────────────────────────────────────────

class UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP over a Unix domain socket (Firecracker API)."""

    def __init__(self, socket_path: str):
        super().__init__("localhost")
        self._socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self._socket_path)


def fc_request(conn: UnixHTTPConnection, method: str, path: str, body: dict) -> tuple[bool, str]:
    """Send a request to the Firecracker API. Returns (ok, response_body)."""
    conn.request(method, path, body=json.dumps(body), headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    resp_body = resp.read().decode()
    if resp.status >= 300:
        log.error("Firecracker API error: %s %s → %s %s", method, path, resp.status, resp_body)
        return False, resp_body
    return True, resp_body


def fc_put(conn: UnixHTTPConnection, path: str, body: dict) -> tuple[bool, str]:
    """PUT request to Firecracker API."""
    return fc_request(conn, "PUT", path, body)


def fc_patch(conn: UnixHTTPConnection, path: str, body: dict) -> tuple[bool, str]:
    """PATCH request to Firecracker API."""
    return fc_request(conn, "PATCH", path, body)


def wait_for_socket(path: str, timeout: float = 5.0) -> bool:
    """Block until a Unix socket file appears on disk."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(path):
            return True
        time.sleep(0.02)
    return False


# ─── VM file management ─────────────────────────────────────────────────────

def prepare_vm_files(vm_id: str) -> tuple[str, str, str]:
    """Create socket, log, and overlay paths for a VM."""
    sock_path = os.path.join(SOCKETS_DIR, f"{vm_id}.sock")
    log_path = f"/tmp/fc_{vm_id}.log"
    overlay_path = os.path.join(OVERLAYS_DIR, f"{vm_id}.ext4")

    shutil.copy2(BASE_ROOTFS_PATH, overlay_path)
    for f in (sock_path, log_path):
        if os.path.exists(f):
            os.remove(f)
    pathlib.Path(log_path).touch()

    return sock_path, log_path, overlay_path


def configure_vm(conn: UnixHTTPConnection, kernel_path: str, rootfs_path: str, vcpus: int, memory_mb: int) -> None:
    """Configure boot source, drive, and machine for a Firecracker VM."""
    fc_put(conn, "/boot-source", {
        "kernel_image_path": kernel_path,
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off init=/init",
    })
    fc_put(conn, "/drives/rootfs", {
        "drive_id": "rootfs", "path_on_host": rootfs_path,
        "is_root_device": True, "is_read_only": False,
    })
    fc_put(conn, "/machine-config", {"vcpu_count": vcpus, "mem_size_mib": memory_mb})


# ─── Rootfs I/O ─────────────────────────────────────────────────────────────

def inject_code_into_rootfs(overlay_path: str, code: str) -> None:
    """Mount rootfs overlay, write code + init script, unmount."""
    mount_dir = f"/tmp/mount_{uuid.uuid4().hex[:8]}"
    os.makedirs(mount_dir, exist_ok=True)
    try:
        subprocess.run(["mount", "-o", "loop", overlay_path, mount_dir], check=True, capture_output=True)
        os.makedirs(os.path.join(mount_dir, "tmp", "output"), exist_ok=True)
        with open(os.path.join(mount_dir, "tmp", "user_code.py"), "w") as f:
            f.write(code)
        init_script = (
            "#!/bin/sh\n"
            "mount -t proc proc /proc 2>/dev/null\n"
            "mount -t sysfs sysfs /sys 2>/dev/null\n"
            "mount -t devtmpfs devtmpfs /dev 2>/dev/null\n"
            "/usr/bin/python3 /tmp/user_code.py > /tmp/output/stdout.txt 2> /tmp/output/stderr.txt\n"
            "echo $? > /tmp/output/exit_code.txt\n"
            "sync\n"
            "/bin/busybox reboot -f\n"
        )
        init_path = os.path.join(mount_dir, "init")
        with open(init_path, "w") as f:
            f.write(init_script)
        os.chmod(init_path, 0o755)
    finally:
        subprocess.run(["umount", mount_dir], check=False, capture_output=True)
        try:
            os.rmdir(mount_dir)
        except OSError:
            pass


def read_result_from_rootfs(overlay_path: str) -> dict:
    """Mount overlay read-only and extract execution results."""
    mount_dir = f"/tmp/read_{uuid.uuid4().hex[:8]}"
    os.makedirs(mount_dir, exist_ok=True)
    stdout = stderr = ""
    exit_code = -1
    try:
        subprocess.run(["mount", "-o", "loop,ro", overlay_path, mount_dir], check=True, capture_output=True)
        out_dir = os.path.join(mount_dir, "tmp", "output")
        for name, target in (("stdout.txt", "stdout"), ("stderr.txt", "stderr"), ("exit_code.txt", "exit_code")):
            fpath = os.path.join(out_dir, name)
            if not os.path.exists(fpath):
                continue
            with open(fpath) as fh:
                val = fh.read()
            if target == "stdout":
                stdout = val.rstrip()
            elif target == "stderr":
                stderr = val.rstrip()
            elif target == "exit_code":
                try:
                    exit_code = int(val.strip())
                except ValueError:
                    pass
    finally:
        subprocess.run(["umount", mount_dir], check=False, capture_output=True)
        try:
            os.rmdir(mount_dir)
        except OSError:
            pass

    return {"success": exit_code == 0, "output": stdout, "error": stderr or None, "exit_code": exit_code}
