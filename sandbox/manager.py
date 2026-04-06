"""AutoFyn Sandbox Manager — unified HTTP API for code execution.

Auto-detects the best available backend:
  - /dev/kvm present → Firecracker microVMs (snapshot-accelerated, ~200ms)
  - No /dev/kvm      → gVisor sandbox (user-space kernel, ~50ms)

Both backends implement ExecutorBase, so the HTTP layer is identical
regardless of which backend is active.
"""

import asyncio
import logging
import os

from aiohttp import web

from config.loader import sandbox_config
from base import ExecutorBase

cfg = sandbox_config()

logging.basicConfig(level=getattr(logging, cfg.get("log_level", "info").upper()))
log = logging.getLogger("sandbox.manager")


# ─── Backend detection ───────────────────────────────────────────────────────

def _detect_executor() -> ExecutorBase:
    """Pick the best executor for this environment."""
    if os.path.exists("/dev/kvm"):
        from firecracker.executor import FirecrackerExecutor
        log.info("KVM detected — using Firecracker backend")
        return FirecrackerExecutor(
            cfg["max_vms"], cfg["vm_memory_mb"],
            cfg["vm_vcpus"], cfg["vm_timeout_sec"],
        )

    from gvisor import GVisorExecutor
    log.info("No KVM — using gVisor backend")
    return GVisorExecutor(cfg["max_vms"], cfg["vm_timeout_sec"])


# ─── HTTP handlers ───────────────────────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    """Return executor health status."""
    executor: ExecutorBase = request.app["executor"]
    status = executor.health()
    status["status"] = "healthy"
    return web.json_response(status)


async def handle_execute(request: web.Request) -> web.Response:
    """Execute code in sandbox."""
    executor: ExecutorBase = request.app["executor"]
    body = await request.json()

    code = body.get("code")
    if not code:
        return web.json_response({"error": "code is required"}, status=400)

    timeout = body.get("timeout", cfg["vm_timeout_sec"])
    result = await executor.execute(code, timeout=timeout)
    status = 200 if result["success"] else 422
    return web.json_response(result, status=status)


async def handle_kill(request: web.Request) -> web.Response:
    """Kill a specific sandbox execution."""
    executor: ExecutorBase = request.app["executor"]
    vm_id = request.match_info["vm_id"]
    executor.cleanup_vm(vm_id)
    return web.json_response({"status": "killed", "vm_id": vm_id})


async def handle_status(request: web.Request) -> web.Response:
    """List active sandbox executions."""
    executor: ExecutorBase = request.app["executor"]
    return web.json_response({"active_vms": executor.list_vms()})


# ─── App lifecycle ───────────────────────────────────────────────────────────

async def _cleanup_expired(app: web.Application) -> None:
    """Periodically kill VMs that exceed the timeout."""
    executor: ExecutorBase = app["executor"]
    timeout = cfg["vm_timeout_sec"]
    while True:
        for vm in executor.list_vms():
            if vm["uptime_sec"] > timeout:
                log.warning("VM %s expired, killing", vm["vm_id"])
                executor.cleanup_vm(vm["vm_id"])
        await asyncio.sleep(10)


async def on_startup(app: web.Application) -> None:
    """Initialize executor and start cleanup task."""
    executor = _detect_executor()
    await executor.start()
    app["executor"] = executor
    app["cleanup_task"] = asyncio.create_task(_cleanup_expired(app))


async def on_shutdown(app: web.Application) -> None:
    """Cancel cleanup and kill all active VMs."""
    app["cleanup_task"].cancel()
    executor: ExecutorBase = app["executor"]
    for vm in executor.list_vms():
        executor.cleanup_vm(vm["vm_id"])


def main() -> None:
    """Start the sandbox HTTP server."""
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    app.router.add_get("/health", handle_health)
    app.router.add_post("/execute", handle_execute)
    app.router.add_delete("/vm/{vm_id}", handle_kill)
    app.router.add_get("/vms", handle_status)

    log.info("Sandbox manager starting on :8080")
    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
