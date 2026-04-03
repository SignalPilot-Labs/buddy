"""Firecracker executor — snapshot-accelerated microVM execution.

Used on Linux hosts where /dev/kvm is available. Boots a template VM once,
snapshots it with Python pre-loaded, then restores from snapshot for each
execution (~200ms vs ~1600ms cold boot).
"""

import asyncio
import json
import logging
import os
import pathlib
import subprocess
import time

from base import ExecutorBase
from firecracker.api import (
    KERNEL_PATH, BASE_ROOTFS_PATH, SNAPSHOT_DIR, OVERLAYS_DIR, SOCKETS_DIR,
    SNAP_FILE, MEM_FILE,
    UnixHTTPConnection, fc_put, fc_patch, wait_for_socket,
    prepare_vm_files, configure_vm, inject_code_into_rootfs, read_result_from_rootfs,
)

log = logging.getLogger("firecracker.executor")


class FirecrackerExecutor(ExecutorBase):
    """Firecracker microVM executor with snapshot acceleration."""

    def __init__(self, max_vms: int, vm_memory_mb: int, vm_vcpus: int, vm_timeout_sec: int):
        super().__init__(max_vms, vm_timeout_sec)
        self._vm_memory_mb = vm_memory_mb
        self._vm_vcpus = vm_vcpus
        self._snapshot_ready = False

    async def start(self) -> None:
        """Create dirs and build snapshot."""
        for d in (SNAPSHOT_DIR, OVERLAYS_DIR, SOCKETS_DIR):
            os.makedirs(d, exist_ok=True)
        self._create_snapshot()

    def health(self) -> dict:
        """Return Firecracker-specific health info."""
        return {
            "backend": "firecracker",
            "kvm_available": os.path.exists("/dev/kvm"),
            "snapshot_ready": self._snapshot_ready,
            "active_vms": len(self._active),
            "max_vms": self._max_vms,
        }

    def _kill_process(self, entry: dict) -> None:
        """Kill the Firecracker process."""
        proc = entry.get("process")
        if proc and proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

    def _cleanup_resources(self, entry: dict) -> None:
        """Remove socket and overlay files."""
        for key in ("socket_path", "overlay_path"):
            path = entry.get(key)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    async def _run(self, code: str, timeout: int, vm_id: str) -> dict:
        """Execute code via snapshot restore or cold boot."""
        if self._snapshot_ready:
            return await self._execute_snapshot(code, timeout, vm_id)
        return await self._execute_cold(code, timeout, vm_id)

    # ── Snapshot creation (runs once at startup) ─────────────────────────

    def _create_snapshot(self) -> None:
        """Boot a template VM, wait for Python readiness, snapshot it."""
        if os.path.exists(SNAP_FILE) and os.path.exists(MEM_FILE):
            log.info("Existing snapshot found, reusing")
            self._snapshot_ready = True
            return

        log.info("Creating template VM for snapshot...")
        sock_path = os.path.join(SOCKETS_DIR, "template.sock")
        log_path = "/tmp/fc_template.log"

        for f in (sock_path, log_path):
            if os.path.exists(f):
                os.remove(f)
        pathlib.Path(log_path).touch()

        proc = subprocess.Popen(
            ["/usr/local/bin/firecracker", "--api-sock", sock_path, "--log-path", log_path, "--level", "Info"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        if not wait_for_socket(sock_path):
            log.error("Template Firecracker socket never appeared")
            proc.kill()
            return

        conn = UnixHTTPConnection(sock_path)
        configure_vm(conn, KERNEL_PATH, BASE_ROOTFS_PATH, self._vm_vcpus, self._vm_memory_mb)

        start = time.monotonic()
        ok, _ = fc_put(conn, "/actions", {"action_type": "InstanceStart"})
        if not ok:
            log.error("Failed to boot template VM")
            proc.kill()
            return

        log.info("Template VM booted in %.0fms", (time.monotonic() - start) * 1000)

        if not self._wait_for_ready(proc, timeout_sec=30):
            log.error("Template VM never became ready")
            proc.kill()
            return

        log.info("Template Python ready in %.0fms — creating snapshot", (time.monotonic() - start) * 1000)

        ok, _ = fc_patch(conn, "/vm", {"state": "Paused"})
        if not ok:
            log.error("Failed to pause template VM")
            proc.kill()
            return

        ok, _ = fc_put(conn, "/snapshot/create", {
            "snapshot_type": "Full", "snapshot_path": SNAP_FILE, "mem_file_path": MEM_FILE,
        })
        if not ok:
            log.error("Failed to create snapshot")
            proc.kill()
            return

        log.info("Snapshot created: state=%.0fKB mem=%.1fMB",
                 os.path.getsize(SNAP_FILE) / 1024, os.path.getsize(MEM_FILE) / (1024 * 1024))

        proc.kill()
        proc.wait()
        if os.path.exists(sock_path):
            os.remove(sock_path)

        self._snapshot_ready = True

    def _wait_for_ready(self, proc: subprocess.Popen[bytes], timeout_sec: int) -> bool:
        """Read VM stdout until ===SP_READY=== appears."""
        if proc.stdout is None:
            return False
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            if line.decode("utf-8", errors="replace").strip() == "===SP_READY===":
                return True
        return False

    # ── Execution modes ──────────────────────────────────────────────────

    async def _execute_snapshot(self, code: str, timeout: int, vm_id: str) -> dict:
        """Restore VM from snapshot, send code via serial, return result."""
        sock_path, log_path, overlay_path = prepare_vm_files(vm_id)
        start_time = time.monotonic()

        proc = subprocess.Popen(
            ["/usr/local/bin/firecracker", "--api-sock", sock_path, "--log-path", log_path,
             "--level", "Info", "--id", vm_id],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self._register(vm_id, process=proc, socket_path=sock_path, overlay_path=overlay_path)

        if not wait_for_socket(sock_path):
            raise RuntimeError("Firecracker socket never appeared")

        conn = UnixHTTPConnection(sock_path)

        ok, err = fc_put(conn, "/snapshot/load", {
            "snapshot_path": SNAP_FILE,
            "mem_backend": {"backend_path": MEM_FILE, "backend_type": "File"},
            "enable_diff_snapshots": False,
        })
        if not ok:
            raise RuntimeError(f"Snapshot load failed: {err}")

        restore_ms = (time.monotonic() - start_time) * 1000

        ok, err = fc_patch(conn, "/vm", {"state": "Resumed"})
        if not ok:
            raise RuntimeError(f"Resume failed: {err}")

        log.info("VM %s restored in %.0fms", vm_id, restore_ms)

        payload = code + "\n===SP_CODE_END===\n"
        if proc.stdin is not None:
            try:
                proc.stdin.write(payload.encode())
                proc.stdin.flush()
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass

        raw = await self._collect_output(proc, timeout)
        result = self._parse_serial_result(raw)
        result["restore_ms"] = restore_ms
        return result

    async def _execute_cold(self, code: str, timeout: int, vm_id: str) -> dict:
        """Boot a fresh VM, inject code via rootfs, return result."""
        sock_path, log_path, overlay_path = prepare_vm_files(vm_id)
        inject_code_into_rootfs(overlay_path, code)

        proc = subprocess.Popen(
            ["/usr/local/bin/firecracker", "--api-sock", sock_path, "--log-path", log_path,
             "--level", "Info", "--id", vm_id],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self._register(vm_id, process=proc, socket_path=sock_path, overlay_path=overlay_path)

        if not wait_for_socket(sock_path):
            raise RuntimeError("Firecracker socket never appeared")

        conn = UnixHTTPConnection(sock_path)
        configure_vm(conn, KERNEL_PATH, overlay_path, self._vm_vcpus, self._vm_memory_mb)

        boot_start = time.monotonic()
        fc_put(conn, "/actions", {"action_type": "InstanceStart"})
        boot_ms = (time.monotonic() - boot_start) * 1000

        await self._wait_for_exit(proc, timeout)

        result = read_result_from_rootfs(overlay_path)
        result["boot_ms"] = boot_ms
        return result

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _collect_output(self, proc: subprocess.Popen[bytes], timeout: int) -> str:
        """Read all stdout from a Firecracker process."""
        if proc.stdout is None:
            return ""
        loop = asyncio.get_running_loop()
        stdout_pipe = proc.stdout

        def _read():
            try:
                stdout_bytes = stdout_pipe.read()
                proc.wait(timeout=timeout)
                return stdout_bytes.decode("utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                return (stdout_pipe.read() or b"").decode("utf-8", errors="replace")

        try:
            return await asyncio.wait_for(loop.run_in_executor(None, _read), timeout=timeout + 2)
        except asyncio.TimeoutError:
            return ""

    def _parse_serial_result(self, raw: str) -> dict:
        """Extract JSON result from serial console output."""
        raw_clean = raw.replace("\r\n", "\n")
        if "===SP_RESULT_START===" in raw_clean and "===SP_RESULT_END===" in raw_clean:
            result_json = raw_clean.split("===SP_RESULT_START===\n", 1)[1].split("\n===SP_RESULT_END===", 1)[0].strip()
            try:
                return json.loads(result_json)
            except json.JSONDecodeError:
                pass

        return {
            "success": False, "output": "", "error": "Execution timed out or produced no result",
            "exit_code": -1,
        }

    async def _wait_for_exit(self, proc: subprocess.Popen[bytes], timeout: int) -> None:
        """Wait for Firecracker process to exit within timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return
            await asyncio.sleep(0.1)
        proc.kill()
        proc.wait()
