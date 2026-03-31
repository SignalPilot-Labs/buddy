"""
Boot a Firecracker microVM and capture its serial console output.

This is the simplest possible Firecracker test:
  1. Start the Firecracker process (creates API socket)
  2. Configure kernel + rootfs + machine via REST API
  3. Boot the VM
  4. Read serial output (the VM prints a banner + runs Python)
  5. VM auto-shuts down after 3 seconds
"""

import json
import os
import socket
import subprocess
import sys
import time
import http.client

KERNEL_PATH = "/opt/vmlinux.bin"
ROOTFS_PATH = "/opt/rootfs.ext4"
SOCKET_PATH = "/tmp/firecracker.sock"
LOG_PATH = "/tmp/firecracker.log"

# Firecracker API talks over a Unix socket using HTTP
class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path):
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


def api_put(conn, path, body):
    """PUT JSON to the Firecracker API."""
    data = json.dumps(body)
    conn.request("PUT", path, body=data, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    resp_body = resp.read().decode()
    if resp.status >= 300:
        print(f"  API error on PUT {path}: {resp.status} {resp_body}")
        return False
    return True


def main():
    print("=" * 50)
    print("  SignalPilot Firecracker VM Boot Test")
    print("=" * 50)
    print()

    # Check prerequisites
    if not os.path.exists("/dev/kvm"):
        print("[FAIL] /dev/kvm not found!")
        print("       Run with: docker run --device /dev/kvm ...")
        sys.exit(1)
    print("[OK] /dev/kvm available")

    if not os.path.exists(KERNEL_PATH):
        print(f"[FAIL] Kernel not found at {KERNEL_PATH}")
        sys.exit(1)
    print(f"[OK] Kernel: {KERNEL_PATH} ({os.path.getsize(KERNEL_PATH) // 1024 // 1024}MB)")

    if not os.path.exists(ROOTFS_PATH):
        print(f"[FAIL] Rootfs not found at {ROOTFS_PATH}")
        sys.exit(1)
    print(f"[OK] Rootfs: {ROOTFS_PATH} ({os.path.getsize(ROOTFS_PATH) // 1024 // 1024}MB)")

    # Clean up any previous socket/log
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    # Firecracker requires the log file to exist before starting
    os.makedirs(os.path.dirname(LOG_PATH) if os.path.dirname(LOG_PATH) else ".", exist_ok=True)
    with open(LOG_PATH, "w") as f:
        pass

    # Start Firecracker process
    print()
    print("[...] Starting Firecracker process...")
    fc_proc = subprocess.Popen(
        [
            "/usr/local/bin/firecracker",
            "--api-sock", SOCKET_PATH,
            "--log-path", LOG_PATH,
            "--level", "Info",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for socket
    for i in range(50):
        if os.path.exists(SOCKET_PATH):
            break
        # Check if process died
        if fc_proc.poll() is not None:
            stdout = fc_proc.stdout.read().decode() if fc_proc.stdout else ""
            stderr = fc_proc.stderr.read().decode() if fc_proc.stderr else ""
            print(f"[FAIL] Firecracker exited early with code {fc_proc.returncode}")
            if stdout:
                print(f"  stdout: {stdout[:500]}")
            if stderr:
                print(f"  stderr: {stderr[:500]}")
            if os.path.exists(LOG_PATH):
                with open(LOG_PATH) as f:
                    print(f"  log: {f.read()[:500]}")
            sys.exit(1)
        time.sleep(0.1)
    else:
        # Process still alive but no socket
        stdout = fc_proc.stdout.read(1024) if fc_proc.stdout else b""
        stderr = fc_proc.stderr.read(1024) if fc_proc.stderr else b""
        print("[FAIL] Firecracker socket never appeared!")
        print(f"  process alive: {fc_proc.poll() is None}")
        print(f"  stderr: {stderr.decode()[:500]}")
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH) as f:
                print(f"  log: {f.read()[:500]}")
        fc_proc.kill()
        sys.exit(1)
    print("[OK] Firecracker API socket ready")

    # Connect to API
    conn = UnixHTTPConnection(SOCKET_PATH)

    # Configure the VM
    print()
    print("[...] Configuring VM...")

    # Set kernel
    ok = api_put(conn, "/boot-source", {
        "kernel_image_path": KERNEL_PATH,
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off init=/init",
    })
    print(f"  {'[OK]' if ok else '[FAIL]'} Kernel configured")

    # Set rootfs
    ok = api_put(conn, "/drives/rootfs", {
        "drive_id": "rootfs",
        "path_on_host": ROOTFS_PATH,
        "is_root_device": True,
        "is_read_only": False,
    })
    print(f"  {'[OK]' if ok else '[FAIL]'} Rootfs configured")

    # Set machine config
    ok = api_put(conn, "/machine-config", {
        "vcpu_count": 1,
        "mem_size_mib": 256,
    })
    print(f"  {'[OK]' if ok else '[FAIL]'} Machine: 1 vCPU, 256MB RAM")

    # Boot!
    print()
    print("[...] Booting microVM...")
    start_time = time.monotonic()

    ok = api_put(conn, "/actions", {
        "action_type": "InstanceStart",
    })

    boot_time = (time.monotonic() - start_time) * 1000
    print(f"  {'[OK]' if ok else '[FAIL]'} VM started in {boot_time:.0f}ms")

    if not ok:
        print()
        print("Boot failed. Firecracker log:")
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH) as f:
                print(f.read())
        fc_proc.kill()
        sys.exit(1)

    # Wait for VM to run and shut itself down
    print()
    print("─── VM Serial Console Output ─────────────────────")
    print()

    try:
        # The VM will run for ~3 seconds then poweroff
        fc_proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        print("(VM didn't shut down in 15s, killing...)")
        fc_proc.kill()
        fc_proc.wait()

    # Print any stdout/stderr from Firecracker (contains serial console)
    stdout = fc_proc.stdout.read().decode() if fc_proc.stdout else ""
    stderr = fc_proc.stderr.read().decode() if fc_proc.stderr else ""

    if stdout:
        print(stdout)
    if stderr:
        print(stderr)

    # Also check the log file
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            log_content = f.read()
            if "Running" in log_content or "started" in log_content.lower():
                print("[OK] Firecracker log confirms VM ran successfully")

    print()
    print("─── End Console Output ───────────────────────────")
    print()
    print(f"VM exited with code: {fc_proc.returncode}")
    print()

    if fc_proc.returncode in (0, -9, 137):
        print("=" * 50)
        print("  SUCCESS — Firecracker is working on your system!")
        print("=" * 50)
        print()
        print("  Your Ryzen 9 9950X3D + Windows 11 + WSL2 + Docker")
        print("  can run Firecracker microVMs.")
        print()
        print(f"  Boot time: {boot_time:.0f}ms")
        print("  Next step: build the full SignalPilot sandbox rootfs")
    else:
        print("=" * 50)
        print(f"  VM exited unexpectedly (code {fc_proc.returncode})")
        print("=" * 50)

    # Cleanup
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)


if __name__ == "__main__":
    main()
