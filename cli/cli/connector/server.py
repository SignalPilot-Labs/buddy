"""Connector HTTP server — bridges agent to remote sandboxes via SSH.

Runs on the host (not in Docker). Manages SSH connections, tunnels,
and reverse-proxies sandbox HTTP traffic.
"""

import argparse
import asyncio
import collections
import hmac
import json
import logging
import os
import shlex
from collections.abc import AsyncGenerator
from typing import Any, Callable, Awaitable

import httpx
from aiohttp import web

from cli.connector.constants import (
    CONNECTOR_BIND_HOST,
    CONNECTOR_DEFAULT_PORT,
    CONNECTOR_SECRET_ENV,
    CONNECTOR_SECRET_HEADER,
    DEFAULT_LOG_TAIL,
    HEARTBEAT_CLIENT_TIMEOUT_SEC,
    HEARTBEAT_INTERVAL_SEC,
    HEARTBEAT_MAX_FAILURES,
    RING_BUFFER_MAX_LINES,
    SANDBOX_HEARTBEAT_TIMEOUT_SEC,
    SANDBOX_QUEUE_TIMEOUT_SEC,
    SANDBOX_SECRET_HEADER,
    SHUTDOWN_TIMEOUT_SEC,
    SSH_CONNECT_TIMEOUT_SEC,
)
from cli.connector.forward_state import ForwardState
from cli.connector.proxy import handle_proxy
from cli.connector.ssh import (
    find_free_port,
    kill_process_group,
    open_ssh_tunnel,
    run_derived_stop,
    run_ssh_command,
)
from cli.connector.startup import stream_start_events

log = logging.getLogger("connector.server")

HandlerType = Callable[[web.Request], Awaitable[web.StreamResponse]]


def _build_image_check(sandbox_type: str, start_cmd: str) -> tuple[str, str] | None:
    """Extract the image path from a start command and build a check command.

    Returns (check_command, image_path) or None if no image found.
    """
    if not start_cmd:
        return None
    if sandbox_type == "slurm":
        for part in start_cmd.split():
            if part.endswith(".sif"):
                expanded = part.replace("~", "$HOME", 1) if part.startswith("~") else part
                return f"test -f {expanded}", part
    elif sandbox_type == "docker":
        for part in start_cmd.split():
            if "/" in part and (":" in part or "." in part):
                return f"docker image inspect {shlex.quote(part)} > /dev/null 2>&1", part
    return None


class ConnectorServer:
    """Async HTTP server managing remote sandbox tunnels."""

    def __init__(self, secret: str, port: int) -> None:
        """Initialize the connector with auth secret and listen port."""
        self._secret = secret
        self._port = port
        self._states: dict[str, ForwardState] = {}
        self._heartbeat_tasks: dict[str, asyncio.Task[None]] = {}
        self._drain_tasks: dict[str, asyncio.Task[None]] = {}
        self._app = web.Application(middlewares=[self._auth_middleware])
        self._register_routes()

    @web.middleware
    async def _auth_middleware(
        self,
        request: web.Request,
        handler: HandlerType,
    ) -> web.StreamResponse:
        """Require X-Connector-Secret on control endpoints.

        Proxy paths (/sandboxes/{run_key}/...) are authenticated by
        the sandbox itself via X-Internal-Secret — no connector auth needed.
        """
        if request.path == "/health":
            return await handler(request)
        if "/sandboxes/" in request.path and request.match_info.get("path") is not None:
            return await handler(request)
        provided = request.headers.get(CONNECTOR_SECRET_HEADER, "")
        if not hmac.compare_digest(provided, self._secret):
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    def _register_routes(self) -> None:
        """Wire up all HTTP routes."""
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_post("/sandboxes/start", self._handle_start)
        self._app.router.add_post("/sandboxes/stop", self._handle_stop)
        self._app.router.add_post("/shutdown", self._handle_shutdown)
        self._app.router.add_post("/sandboxes/test", self._handle_test)
        self._app.router.add_get(
            "/sandboxes/{run_key}/logs", self._handle_logs,
        )
        self._app.router.add_route(
            "*", "/sandboxes/{run_key}/{path:.*}", self._handle_proxy,
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Return connector health — non-sensitive info only."""
        return web.json_response({"status": "ok", "tunnel_count": len(self._states)})

    async def _handle_test(self, request: web.Request) -> web.Response:
        """Test SSH connection and sandbox image availability."""
        body: dict[str, Any] = await request.json()
        ssh_target: str = body["ssh_target"]
        sandbox_type: str = body["sandbox_type"]
        start_cmd: str = body.get("start_cmd", "")

        checks: list[dict[str, str | bool]] = []

        # Check 1: SSH connectivity
        try:
            proc = await run_ssh_command(ssh_target, "echo ok", {})
            await asyncio.wait_for(proc.communicate(), timeout=SSH_CONNECT_TIMEOUT_SEC)
            ssh_ok = proc.returncode == 0
            checks.append({"name": "ssh", "ok": ssh_ok, "detail": "Connected" if ssh_ok else f"Exit {proc.returncode}"})
        except asyncio.TimeoutError:
            checks.append({"name": "ssh", "ok": False, "detail": "Timeout"})
            return web.json_response({"ok": False, "checks": checks})
        except Exception as exc:
            checks.append({"name": "ssh", "ok": False, "detail": str(exc)})
            return web.json_response({"ok": False, "checks": checks})

        # Check 2: sandbox image exists — extract image path from start command
        image_check = _build_image_check(sandbox_type, start_cmd)
        if image_check:
            check_cmd, image_path = image_check
            try:
                proc = await run_ssh_command(ssh_target, check_cmd, {})
                await asyncio.wait_for(proc.communicate(), timeout=SSH_CONNECT_TIMEOUT_SEC)
                img_ok = proc.returncode == 0
                detail = f"Found ({image_path})" if img_ok else f"Not found at {image_path}"
                checks.append({"name": "image", "ok": img_ok, "detail": detail})
            except asyncio.TimeoutError:
                checks.append({"name": "image", "ok": False, "detail": f"Timeout checking {image_path}"})
            except Exception as exc:
                checks.append({"name": "image", "ok": False, "detail": str(exc)})

        all_ok = all(c["ok"] for c in checks)
        return web.json_response({"ok": all_ok, "checks": checks})

    async def _handle_start(self, request: web.Request) -> web.StreamResponse:
        """Start a remote sandbox — NDJSON streaming response."""
        body: dict[str, Any] = await request.json()
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={"Content-Type": "application/x-ndjson"},
        )
        await response.prepare(request)

        try:
            await self._execute_start(body, response)
        except Exception as exc:
            log.error("Start failed: %s", exc)
            fail_event = {"event": "failed", "error": str(exc)}
            await response.write((json.dumps(fail_event) + "\n").encode())

        await response.write_eof()
        return response

    async def _execute_start(
        self,
        body: dict[str, Any],
        response: web.StreamResponse,
    ) -> None:
        """Execute the start sequence: run command, setup tunnel, track state."""
        run_key: str = body["run_key"]
        ssh_target: str = body["ssh_target"]
        sandbox_type: str = body["sandbox_type"]
        start_cmd: str = body["start_cmd"]
        host_mounts: list[dict[str, str]] = body["host_mounts"]
        heartbeat_timeout: int = body.get(
            "heartbeat_timeout", SANDBOX_HEARTBEAT_TIMEOUT_SEC,
        )

        if run_key in self._states:
            raise RuntimeError(f"Run {run_key} already has an active tunnel")

        process, event_gen = await asyncio.wait_for(
            stream_start_events(
                ssh_target=ssh_target,
                start_cmd=start_cmd,
                run_key=run_key,
                sandbox_type=sandbox_type,
                host_mounts=host_mounts,
                heartbeat_timeout=heartbeat_timeout,
            ),
            timeout=SANDBOX_QUEUE_TIMEOUT_SEC,
        )

        try:
            events, ready_event = await asyncio.wait_for(
                self._stream_and_collect(event_gen, response),
                timeout=SANDBOX_QUEUE_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            await event_gen.aclose()
            await kill_process_group(process)
            raise

        if not ready_event:
            await kill_process_group(process)
            log_lines = [
                e["line"] for e in events if e.get("event") == "log"
            ]
            tail = "\n".join(log_lines[-10:]) if log_lines else "(no output)"
            fail = {"event": "failed", "error": f"Start command exited without AF_READY:\n{tail}"}
            await response.write((json.dumps(fail) + "\n").encode())
            return

        try:
            state = await self._create_forward_state(
                run_key, ssh_target, sandbox_type,
                ready_event, events, process,
            )
        except Exception:
            await kill_process_group(process)
            raise
        self._states[run_key] = state

        if process.stdout:
            task = asyncio.create_task(self._drain_logs(run_key, process))
            self._drain_tasks[run_key] = task

        self._heartbeat_tasks[run_key] = asyncio.create_task(
            self._heartbeat_loop(run_key),
        )

    async def _stream_and_collect(
        self,
        event_gen: AsyncGenerator[dict[str, Any], None],
        response: web.StreamResponse,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Stream events from generator to response, collecting them.

        Returns (all_events, ready_event_or_None).
        """
        events: list[dict[str, Any]] = []
        ready_event: dict[str, Any] | None = None
        async for event in event_gen:
            await response.write((json.dumps(event) + "\n").encode())
            events.append(event)
            if event.get("event") == "ready":
                ready_event = event
                break
        return events, ready_event

    async def _create_forward_state(
        self,
        run_key: str,
        ssh_target: str,
        sandbox_type: str,
        ready_event: dict[str, Any],
        events: list[dict[str, Any]],
        process: asyncio.subprocess.Process,
    ) -> ForwardState:
        """Open SSH tunnel and build ForwardState."""
        remote_host: str = ready_event["host"]
        remote_port: int = ready_event["port"]
        sandbox_secret: str | None = ready_event.get("sandbox_secret")
        if not sandbox_secret:
            raise RuntimeError(
                "Sandbox did not provide secret in AF_READY marker — "
                "upgrade sandbox image to a version that generates its own secret"
            )
        backend_id: str | None = next(
            (
                e.get("backend_id")
                for e in events
                if e.get("event") in ("queued", "ready") and e.get("backend_id")
            ),
            None,
        )

        local_port = await find_free_port()
        tunnel = await open_ssh_tunnel(
            ssh_target, remote_host, remote_port, local_port, sandbox_type,
        )

        return ForwardState(
            run_key=run_key,
            ssh_target=ssh_target,
            sandbox_type=sandbox_type,
            local_port=local_port,
            tunnel_process=tunnel,
            start_process=process if sandbox_type == "slurm" else None,
            sandbox_secret=sandbox_secret,
            backend_id=backend_id,
            log_buffer=collections.deque(maxlen=RING_BUFFER_MAX_LINES),
        )

    async def _handle_stop(self, request: web.Request) -> web.Response:
        """Stop a remote sandbox."""
        body: dict[str, Any] = await request.json()
        run_key: str = body["run_key"]
        await self._destroy(run_key)
        return web.json_response({"ok": True})

    async def _handle_shutdown(self, request: web.Request) -> web.Response:
        """Gracefully stop all active remote sandboxes with a single total timeout."""
        keys = list(self._states.keys())

        async def _destroy_all() -> None:
            for key in keys:
                await self._destroy(key)

        try:
            await asyncio.wait_for(_destroy_all(), timeout=SHUTDOWN_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            log.warning(
                "Shutdown timed out after %ds, %d sandboxes remaining",
                SHUTDOWN_TIMEOUT_SEC, len(self._states),
            )
        return web.json_response({"ok": True, "remaining": len(self._states)})

    async def _handle_logs(self, request: web.Request) -> web.Response:
        """Return ring buffer logs for a run."""
        run_key = request.match_info["run_key"]
        tail = int(request.query.get("tail", str(DEFAULT_LOG_TAIL)))
        state = self._states.get(run_key)
        if not state:
            return web.json_response({"lines": [], "total": 0})
        lines = list(state.log_buffer)
        lines = lines[-tail:] if tail < len(lines) else lines
        return web.json_response({"lines": lines, "total": len(lines)})

    async def _handle_proxy(self, request: web.Request) -> web.StreamResponse:
        """Reverse-proxy to sandbox via SSH tunnel."""
        return await handle_proxy(request, self._states)

    async def _destroy(self, run_key: str) -> None:
        """Tear down a remote sandbox: derived stop, kill processes, tunnel, clean up."""
        state = self._states.pop(run_key, None)
        if not state:
            return

        task = self._heartbeat_tasks.pop(run_key, None)
        if task:
            task.cancel()

        drain_task = self._drain_tasks.pop(run_key, None)
        if drain_task:
            drain_task.cancel()

        if state.backend_id:
            try:
                await run_derived_stop(
                    state.ssh_target, state.sandbox_type, state.backend_id,
                )
            except Exception as exc:
                log.warning(
                    "Derived stop failed for %s: %s", run_key, exc,
                )

        if state.start_process:
            await kill_process_group(state.start_process)

        await kill_process_group(state.tunnel_process)

        log.info("Destroyed sandbox %s", run_key)

    async def _drain_logs(
        self,
        run_key: str,
        process: asyncio.subprocess.Process,
    ) -> None:
        """Drain stdout from start process into ring buffer."""
        if not process.stdout:
            return
        try:
            async for line_bytes in process.stdout:
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                state = self._states.get(run_key)
                if state:
                    state.log_buffer.append(line)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            log.debug("Log drain ended for %s: %s", run_key, exc)

    async def _heartbeat_loop(self, run_key: str) -> None:
        """Send periodic heartbeat pings to the remote sandbox."""
        consecutive_failures = 0
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
            state = self._states.get(run_key)
            if not state:
                return
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(HEARTBEAT_CLIENT_TIMEOUT_SEC),
                ) as client:
                    await client.get(
                        f"http://127.0.0.1:{state.local_port}/heartbeat",
                        headers={SANDBOX_SECRET_HEADER: state.sandbox_secret},
                    )
                consecutive_failures = 0
            except Exception:
                consecutive_failures += 1
                log.warning(
                    "Heartbeat failed for %s (%d/%d)",
                    run_key, consecutive_failures, HEARTBEAT_MAX_FAILURES,
                )
                if consecutive_failures >= HEARTBEAT_MAX_FAILURES:
                    log.error(
                        "Heartbeat lost for %s — destroying sandbox",
                        run_key,
                    )
                    await self._destroy(run_key)
                    return

    def run(self) -> None:
        """Start the connector HTTP server."""
        web.run_app(self._app, host=CONNECTOR_BIND_HOST, port=self._port)


def main() -> None:
    """CLI entry point for the connector."""
    logging.basicConfig(level=logging.INFO, format="[connector] %(message)s")
    parser = argparse.ArgumentParser(description="AutoFyn Connector")
    parser.add_argument(
        "--port",
        type=int,
        default=CONNECTOR_DEFAULT_PORT,
        help="Listen port",
    )
    args = parser.parse_args()
    secret = os.environ.get(CONNECTOR_SECRET_ENV, "")
    if not secret:
        raise RuntimeError(f"Missing required env var: {CONNECTOR_SECRET_ENV}")
    server = ConnectorServer(secret, args.port)
    server.run()


if __name__ == "__main__":
    main()
