"""
SignalPilot Sandbox Manager — Snapshot-accelerated Firecracker execution

Performance model:
  Cold boot:  ~1600ms (kernel + Python startup + exec + shutdown)
  Snapshot:   ~200ms  (restore + exec + shutdown)

At startup, we boot a template VM, wait for Python to fully load,
snapshot it, then kill the template. Every subsequent execution restores
from the snapshot — skipping kernel boot and Python interpreter startup.

Communication: serial console (stdin/stdout of the Firecracker process).
The VM's init (sandbox_init.py) reads code from stdin, executes, writes
JSON result to stdout, then reboots.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
import uuid

from aiohttp import web

# ─── Configuration ───────────────────────────────────────────────────────────

GATEWAY_URL = os.getenv("SP_GATEWAY_URL", "http://host.docker.internal:3100")
MAX_VMS = int(os.getenv("SP_MAX_VMS", "10"))
VM_MEMORY_MB = int(os.getenv("SP_VM_MEMORY_MB", "512"))
VM_VCPUS = int(os.getenv("SP_VM_VCPUS", "1"))
VM_TIMEOUT_SEC = int(os.getenv("SP_VM_TIMEOUT_SEC", "300"))
LOG_LEVEL = os.getenv("SP_LOG_LEVEL", "info").upper()

KERNEL_PATH = "/opt/signalpilot/kernel/vmlinux.bin"
BASE_ROOTFS_PATH = "/opt/signalpilot/rootfs/sandbox-rootfs.ext4"
OVERLAYS_DIR = "/opt/signalpilot/overlays"
SOCKETS_DIR = "/opt/signalpilot/sockets"
SNAPSHOT_DIR = "/opt/signalpilot/snapshot"

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
log = logging.getLogger("sandbox_manager")

active_vms: dict[str, dict] = {}

# Snapshot state
snapshot_ready = False
SNAP_FILE = os.path.join(SNAPSHOT_DIR, "vm.snap")
MEM_FILE = os.path.join(SNAPSHOT_DIR, "vm.mem")

# ─── Firecracker API helpers ─────────────────────────────────────────────────

import http.client
import socket


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path):
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


def fc_put(conn, path, body):
    data = json.dumps(body)
    conn.request("PUT", path, body=data, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    resp_body = resp.read().decode()
    if resp.status >= 300:
        log.error(f"Firecracker API error: PUT {path} → {resp.status} {resp_body}")
        return False, resp_body
    return True, resp_body


def fc_patch(conn, path, body):
    data = json.dumps(body)
    conn.request("PATCH", path, body=data, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    resp_body = resp.read().decode()
    if resp.status >= 300:
        log.error(f"Firecracker API error: PATCH {path} → {resp.status} {resp_body}")
        return False, resp_body
    return True, resp_body


def wait_for_socket(path, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(path):
            return True
        time.sleep(0.02)
    return False


# ─── Snapshot creation (runs once at startup) ────────────────────────────────

def create_snapshot():
    """Boot a template VM, wait for Python readiness, snapshot it."""
    global snapshot_ready

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    os.makedirs(OVERLAYS_DIR, exist_ok=True)
    os.makedirs(SOCKETS_DIR, exist_ok=True)

    # If snapshot already exists, reuse it
    if os.path.exists(SNAP_FILE) and os.path.exists(MEM_FILE):
        log.info("Existing snapshot found, reusing")
        snapshot_ready = True
        return

    log.info("Creating template VM for snapshot...")
    sock_path = os.path.join(SOCKETS_DIR, "template.sock")
    log_path = "/tmp/fc_template.log"

    # Clean up
    for f in [sock_path, log_path]:
        if os.path.exists(f):
            os.remove(f)
    open(log_path, "w").close()

    # Start Firecracker
    proc = subprocess.Popen(
        ["/usr/local/bin/firecracker",
         "--api-sock", sock_path,
         "--log-path", log_path,
         "--level", "Info"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not wait_for_socket(sock_path):
        log.error("Template Firecracker socket never appeared")
        proc.kill()
        return

    conn = UnixHTTPConnection(sock_path)

    # Configure and boot
    fc_put(conn, "/boot-source", {
        "kernel_image_path": KERNEL_PATH,
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off init=/init",
    })
    fc_put(conn, "/drives/rootfs", {
        "drive_id": "rootfs",
        "path_on_host": BASE_ROOTFS_PATH,
        "is_root_device": True,
        "is_read_only": False,
    })
    fc_put(conn, "/machine-config", {
        "vcpu_count": VM_VCPUS,
        "mem_size_mib": VM_MEMORY_MB,
    })

    start = time.monotonic()
    ok, _ = fc_put(conn, "/actions", {"action_type": "InstanceStart"})
    if not ok:
        log.error("Failed to boot template VM")
        proc.kill()
        return

    boot_ms = (time.monotonic() - start) * 1000
    log.info(f"Template VM booted in {boot_ms:.0f}ms, waiting for Python readiness...")

    # Read stdout until we see READY marker
    # This means Python has started and pre-imported all modules
    deadline = time.monotonic() + 30
    ready = False
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace").strip()
        if text == "===SP_READY===":
            ready = True
            break

    if not ready:
        log.error("Template VM never became ready")
        proc.kill()
        return

    ready_ms = (time.monotonic() - start) * 1000
    log.info(f"Template Python ready in {ready_ms:.0f}ms — creating snapshot")

    # Pause VM
    ok, _ = fc_patch(conn, "/vm", {"state": "Paused"})
    if not ok:
        log.error("Failed to pause template VM")
        proc.kill()
        return

    # Create snapshot
    ok, _ = fc_put(conn, "/snapshot/create", {
        "snapshot_type": "Full",
        "snapshot_path": SNAP_FILE,
        "mem_file_path": MEM_FILE,
    })
    if not ok:
        log.error("Failed to create snapshot")
        proc.kill()
        return

    snap_size = os.path.getsize(SNAP_FILE) / 1024
    mem_size = os.path.getsize(MEM_FILE) / (1024 * 1024)
    log.info(f"Snapshot created: state={snap_size:.0f}KB mem={mem_size:.1f}MB")

    # Kill template
    proc.kill()
    proc.wait()
    if os.path.exists(sock_path):
        os.remove(sock_path)

    snapshot_ready = True
    log.info("Snapshot ready — all subsequent executions will use restore")


# ─── Execution (restore from snapshot) ───────────────────────────────────────

def cleanup_vm(vm_id: str):
    vm = active_vms.pop(vm_id, None)
    if vm is None:
        return
    proc = vm.get("process")
    if proc and proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    for key in ("socket_path", "overlay_path"):
        path = vm.get(key)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    log.info(f"VM {vm_id} cleaned up")


async def execute_code_snapshot(code: str, timeout: int = 30) -> dict:
    """Restore VM from snapshot, send code via serial, return result."""
    if len(active_vms) >= MAX_VMS:
        raise RuntimeError(f"Max concurrent VMs ({MAX_VMS}) reached")

    vm_id = str(uuid.uuid4())[:8]
    sock_path = os.path.join(SOCKETS_DIR, f"{vm_id}.sock")
    log_path = f"/tmp/fc_{vm_id}.log"

    # Copy the base rootfs as overlay (snapshot restore needs its own drive copy)
    overlay_path = os.path.join(OVERLAYS_DIR, f"{vm_id}.ext4")
    shutil.copy2(BASE_ROOTFS_PATH, overlay_path)

    # Clean up old socket/log
    for f in [sock_path, log_path]:
        if os.path.exists(f):
            os.remove(f)
    open(log_path, "w").close()

    start_time = time.monotonic()

    # Start Firecracker (no boot — we'll load a snapshot)
    proc = subprocess.Popen(
        ["/usr/local/bin/firecracker",
         "--api-sock", sock_path,
         "--log-path", log_path,
         "--level", "Info",
         "--id", vm_id],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    active_vms[vm_id] = {
        "process": proc,
        "socket_path": sock_path,
        "overlay_path": overlay_path,
        "started_at": time.time(),
    }

    try:
        if not wait_for_socket(sock_path):
            raise RuntimeError("Firecracker socket never appeared")

        conn = UnixHTTPConnection(sock_path)

        # Load snapshot
        ok, err = fc_put(conn, "/snapshot/load", {
            "snapshot_path": SNAP_FILE,
            "mem_backend": {
                "backend_path": MEM_FILE,
                "backend_type": "File",
            },
            "enable_diff_snapshots": False,
        })
        if not ok:
            raise RuntimeError(f"Snapshot load failed: {err}")

        restore_ms = (time.monotonic() - start_time) * 1000

        # Resume VM — Python resumes reading from stdin
        ok, err = fc_patch(conn, "/vm", {"state": "Resumed"})
        if not ok:
            raise RuntimeError(f"Resume failed: {err}")

        resume_ms = (time.monotonic() - start_time) * 1000
        log.info(f"VM {vm_id} restored in {restore_ms:.0f}ms, resumed at {resume_ms:.0f}ms")

        # Send code via stdin (serial console), then close stdin
        payload = code + "\n===SP_CODE_END===\n"
        try:
            proc.stdin.write(payload.encode())
            proc.stdin.flush()
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass  # VM may have exited already

        # Wait for process to exit and collect all stdout
        loop = asyncio.get_event_loop()
        result_json = None

        def collect_output():
            try:
                stdout_bytes = proc.stdout.read()
                proc.wait(timeout=timeout)
                return stdout_bytes.decode("utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                return (proc.stdout.read() or b"").decode("utf-8", errors="replace")

        try:
            raw = await asyncio.wait_for(
                loop.run_in_executor(None, collect_output),
                timeout=timeout + 2,
            )
            # Parse result markers from serial output (serial uses \r\n)
            raw_clean = raw.replace("\r\n", "\n")
            if "===SP_RESULT_START===" in raw_clean and "===SP_RESULT_END===" in raw_clean:
                result_json = raw_clean.split("===SP_RESULT_START===\n", 1)[1].split("\n===SP_RESULT_END===", 1)[0].strip()
        except asyncio.TimeoutError:
            pass

        elapsed_ms = (time.monotonic() - start_time) * 1000

        if result_json:
            try:
                result = json.loads(result_json)
                result["vm_id"] = vm_id
                result["restore_ms"] = restore_ms
                result["execution_ms"] = elapsed_ms
                return result
            except json.JSONDecodeError:
                pass

        return {
            "success": False,
            "output": "",
            "error": "Execution timed out or produced no result",
            "exit_code": -1,
            "vm_id": vm_id,
            "restore_ms": restore_ms,
            "execution_ms": elapsed_ms,
        }

    finally:
        cleanup_vm(vm_id)


# ─── Fallback: cold boot execution (used if snapshot not available) ──────────

async def execute_code_cold(code: str, session_token: str, timeout: int = 30) -> dict:
    """Boot a fresh VM, inject code via rootfs, return result."""
    if len(active_vms) >= MAX_VMS:
        raise RuntimeError(f"Max concurrent VMs ({MAX_VMS}) reached")

    vm_id = str(uuid.uuid4())[:8]
    sock_path = os.path.join(SOCKETS_DIR, f"{vm_id}.sock")
    log_path = f"/tmp/fc_{vm_id}.log"
    overlay_path = os.path.join(OVERLAYS_DIR, f"{vm_id}.ext4")

    start_time = time.monotonic()

    # Copy rootfs and inject code
    shutil.copy2(BASE_ROOTFS_PATH, overlay_path)
    mount_dir = f"/tmp/mount_{vm_id}"
    os.makedirs(mount_dir, exist_ok=True)
    try:
        subprocess.run(["mount", "-o", "loop", overlay_path, mount_dir], check=True, capture_output=True)
        os.makedirs(os.path.join(mount_dir, "tmp", "output"), exist_ok=True)
        with open(os.path.join(mount_dir, "tmp", "user_code.py"), "w") as f:
            f.write(code)
        init_script = """#!/bin/sh
mount -t proc proc /proc 2>/dev/null
mount -t sysfs sysfs /sys 2>/dev/null
mount -t devtmpfs devtmpfs /dev 2>/dev/null
/usr/bin/python3 /tmp/user_code.py > /tmp/output/stdout.txt 2> /tmp/output/stderr.txt
echo $? > /tmp/output/exit_code.txt
sync
/bin/busybox reboot -f
"""
        with open(os.path.join(mount_dir, "init"), "w") as f:
            f.write(init_script)
        os.chmod(os.path.join(mount_dir, "init"), 0o755)
    finally:
        subprocess.run(["umount", mount_dir], check=False, capture_output=True)
        try:
            os.rmdir(mount_dir)
        except OSError:
            pass

    open(log_path, "w").close()
    proc = subprocess.Popen(
        ["/usr/local/bin/firecracker", "--api-sock", sock_path, "--log-path", log_path, "--level", "Info", "--id", vm_id],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    active_vms[vm_id] = {"process": proc, "socket_path": sock_path, "overlay_path": overlay_path, "started_at": time.time()}

    try:
        if not wait_for_socket(sock_path):
            raise RuntimeError("Firecracker socket never appeared")
        conn = UnixHTTPConnection(sock_path)
        fc_put(conn, "/boot-source", {"kernel_image_path": KERNEL_PATH, "boot_args": "console=ttyS0 reboot=k panic=1 pci=off init=/init"})
        fc_put(conn, "/drives/rootfs", {"drive_id": "rootfs", "path_on_host": overlay_path, "is_root_device": True, "is_read_only": False})
        fc_put(conn, "/machine-config", {"vcpu_count": VM_VCPUS, "mem_size_mib": VM_MEMORY_MB})
        boot_start = time.monotonic()
        fc_put(conn, "/actions", {"action_type": "InstanceStart"})
        boot_ms = (time.monotonic() - boot_start) * 1000

        # Wait for exit
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            await asyncio.sleep(0.1)
        else:
            proc.kill()
            proc.wait()

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Ensure process is dead
        if proc.poll() is None:
            proc.kill()
            proc.wait()

        # Read output from overlay
        mount_dir = f"/tmp/read_{vm_id}"
        os.makedirs(mount_dir, exist_ok=True)
        stdout = stderr = ""
        exit_code = -1
        try:
            subprocess.run(["mount", "-o", "loop", overlay_path, mount_dir], check=True, capture_output=True)
            for name, target in [("stdout.txt", "stdout"), ("stderr.txt", "stderr"), ("exit_code.txt", "exit_code")]:
                path = os.path.join(mount_dir, "tmp", "output", name)
                if os.path.exists(path):
                    val = open(path).read()
                    if target == "stdout": stdout = val.rstrip()
                    elif target == "stderr": stderr = val.rstrip()
                    elif target == "exit_code":
                        try: exit_code = int(val.strip())
                        except ValueError: pass
        finally:
            subprocess.run(["umount", mount_dir], check=False, capture_output=True)
            try: os.rmdir(mount_dir)
            except OSError: pass

        return {"success": exit_code == 0, "output": stdout, "error": stderr or None, "exit_code": exit_code, "vm_id": vm_id, "boot_ms": boot_ms, "execution_ms": elapsed_ms}
    finally:
        cleanup_vm(vm_id)


# ─── HTTP API ────────────────────────────────────────────────────────────────

async def handle_health(request):
    return web.json_response({
        "status": "healthy" if os.path.exists("/dev/kvm") else "degraded",
        "kvm_available": os.path.exists("/dev/kvm"),
        "active_vms": len(active_vms),
        "max_vms": MAX_VMS,
        "snapshot_ready": snapshot_ready,
    })


async def handle_execute(request):
    body = await request.json()
    code = body.get("code")
    if not code:
        return web.json_response({"error": "code is required"}, status=400)

    timeout = body.get("timeout", VM_TIMEOUT_SEC)

    try:
        if snapshot_ready:
            result = await execute_code_snapshot(code, timeout=timeout)
        else:
            result = await execute_code_cold(code, body.get("session_token", ""), timeout=timeout)
        return web.json_response(result)
    except RuntimeError as e:
        return web.json_response({"error": str(e)}, status=503)
    except Exception as e:
        log.exception("execute error")
        return web.json_response({"error": str(e)}, status=500)


async def handle_kill(request):
    vm_id = request.match_info["vm_id"]
    cleanup_vm(vm_id)
    return web.json_response({"status": "killed", "vm_id": vm_id})


async def handle_status(request):
    vms = [{"vm_id": k, "uptime_sec": time.time() - v["started_at"]} for k, v in active_vms.items()]
    return web.json_response({"active_vms": vms})


async def cleanup_expired_vms():
    while True:
        now = time.time()
        for vm_id in [k for k, v in active_vms.items() if now - v["started_at"] > VM_TIMEOUT_SEC]:
            log.warning(f"VM {vm_id} expired, killing")
            cleanup_vm(vm_id)
        await asyncio.sleep(10)


async def on_startup(app):
    app["cleanup_task"] = asyncio.create_task(cleanup_expired_vms())


async def on_shutdown(app):
    app["cleanup_task"].cancel()
    for vm_id in list(active_vms.keys()):
        cleanup_vm(vm_id)


def main():
    if not os.path.exists("/dev/kvm"):
        log.warning("Starting in degraded mode (no KVM)")

    os.makedirs(OVERLAYS_DIR, exist_ok=True)
    os.makedirs(SOCKETS_DIR, exist_ok=True)

    # Create snapshot at startup
    try:
        create_snapshot()
    except Exception:
        log.exception("Snapshot creation failed — falling back to cold boot")

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/execute", handle_execute)
    app.router.add_delete("/vm/{vm_id}", handle_kill)
    app.router.add_get("/vms", handle_status)

    log.info(f"Sandbox manager starting on :8080 (max {MAX_VMS} VMs, snapshot={'yes' if snapshot_ready else 'no'})")
    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
