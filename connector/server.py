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
from typing import Any, Callable, Awaitable

import httpx
from aiohttp import web

from connector.constants import (
    CONNECTOR_BIND_HOST,
    CONNECTOR_DEFAULT_PORT,
    CONNECTOR_SECRET_HEADER,
    DEFAULT_LOG_TAIL,
    DEFAULT_SECRET_DIR,
    HEARTBEAT_CLIENT_TIMEOUT_SEC,
    HEARTBEAT_INTERVAL_SEC,
    HEARTBEAT_MAX_FAILURES,
    RING_BUFFER_MAX_LINES,
    SHUTDOWN_TIMEOUT_SEC,
)
from connector.forward_state import ForwardState
from connector.proxy import handle_proxy
from connector.ssh import (
    delete_remote_secret,
    find_free_port,
    kill_process_group,
    open_ssh_tunnel,
)
from connector.startup import stream_start_events
from db.constants import SANDBOX_HEARTBEAT_TIMEOUT_SEC, SANDBOX_QUEUE_TIMEOUT_SEC

log = logging.getLogger("connector.server")

HandlerType = Callable[[web.Request], Awaitable[web.StreamResponse]]


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
        """Require X-Connector-Secret on all endpoints except /health."""
        if request.path == "/health":
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
        self._app.router.add_get(
            "/sandboxes/{run_key}/logs", self._handle_logs,
        )
        self._app.router.add_route(
            "*", "/sandboxes/{run_key}/{path:.*}", self._handle_proxy,
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Return connector health with active tunnel info."""
        tunnels = [
            {
                "run_key": s.run_key,
                "ssh_target": s.ssh_target,
                "sandbox_type": s.sandbox_type,
            }
            for s in self._states.values()
        ]
        return web.json_response({"status": "ok", "tunnels": tunnels})

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
        sandbox_secret: str = body["sandbox_secret"]
        start_cmd: str = body["start_cmd"]
        host_mounts: list[dict[str, str]] = body["host_mounts"]
        heartbeat_timeout: int = body.get(
            "heartbeat_timeout", SANDBOX_HEARTBEAT_TIMEOUT_SEC,
        )
        secret_dir: str = body.get("secret_dir", DEFAULT_SECRET_DIR)

        if run_key in self._states:
            raise RuntimeError(f"Run {run_key} already has an active tunnel")

        process, secret_file_path, events = await asyncio.wait_for(
            stream_start_events(
                ssh_target=ssh_target,
                start_cmd=start_cmd,
                run_key=run_key,
                sandbox_secret=sandbox_secret,
                sandbox_type=sandbox_type,
                host_mounts=host_mounts,
                heartbeat_timeout=heartbeat_timeout,
                secret_dir=secret_dir,
            ),
            timeout=SANDBOX_QUEUE_TIMEOUT_SEC,
        )

        for event in events:
            await response.write((json.dumps(event) + "\n").encode())

        ready_event = next(
            (e for e in events if e.get("event") == "ready"), None,
        )
        if not ready_event:
            await kill_process_group(process)
            await delete_remote_secret(ssh_target, secret_file_path)
            fail = {"event": "failed", "error": "Start command exited without AF_READY"}
            await response.write((json.dumps(fail) + "\n").encode())
            return

        try:
            state = await self._create_forward_state(
                run_key, ssh_target, sandbox_type, sandbox_secret,
                ready_event, events, process, secret_file_path,
            )
        except Exception:
            await kill_process_group(process)
            await delete_remote_secret(ssh_target, secret_file_path)
            raise
        self._states[run_key] = state

        if process.stdout:
            task = asyncio.create_task(self._drain_logs(run_key, process))
            self._drain_tasks[run_key] = task

        self._heartbeat_tasks[run_key] = asyncio.create_task(
            self._heartbeat_loop(run_key),
        )

    async def _create_forward_state(
        self,
        run_key: str,
        ssh_target: str,
        sandbox_type: str,
        sandbox_secret: str,
        ready_event: dict[str, Any],
        events: list[dict[str, Any]],
        process: asyncio.subprocess.Process,
        secret_file_path: str,
    ) -> ForwardState:
        """Open SSH tunnel and build ForwardState."""
        remote_host: str = ready_event["host"]
        remote_port: int = ready_event["port"]
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
            ssh_target, remote_host, remote_port, local_port,
        )

        return ForwardState(
            run_key=run_key,
            ssh_target=ssh_target,
            sandbox_type=sandbox_type,
            remote_host=remote_host,
            remote_port=remote_port,
            local_port=local_port,
            tunnel_process=tunnel,
            start_process=process if sandbox_type == "slurm" else None,
            sandbox_secret=sandbox_secret,
            backend_id=backend_id,
            log_buffer=collections.deque(maxlen=RING_BUFFER_MAX_LINES),
            secret_file_path=secret_file_path,
        )

    async def _handle_stop(self, request: web.Request) -> web.Response:
        """Stop a remote sandbox."""
        body: dict[str, Any] = await request.json()
        run_key: str = body["run_key"]
        await self._destroy(run_key)
        return web.json_response({"ok": True})

    async def _handle_shutdown(self, request: web.Request) -> web.Response:
        """Gracefully stop all active remote sandboxes."""
        keys = list(self._states.keys())
        for key in keys:
            try:
                await asyncio.wait_for(
                    self._destroy(key), timeout=SHUTDOWN_TIMEOUT_SEC,
                )
            except (asyncio.TimeoutError, Exception) as exc:
                log.error("Shutdown cleanup failed for %s: %s", key, exc)
        return web.json_response({"ok": True, "stopped": len(keys)})

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
        """Tear down a remote sandbox: kill processes, tunnel, clean up."""
        state = self._states.pop(run_key, None)
        if not state:
            return

        task = self._heartbeat_tasks.pop(run_key, None)
        if task:
            task.cancel()

        drain_task = self._drain_tasks.pop(run_key, None)
        if drain_task:
            drain_task.cancel()

        if state.start_process:
            await kill_process_group(state.start_process)

        await kill_process_group(state.tunnel_process)

        if state.secret_file_path:
            try:
                await delete_remote_secret(state.ssh_target, state.secret_file_path)
            except Exception as exc:
                log.warning(
                    "Failed to delete secret for %s: %s", run_key, exc,
                )

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
                        f"http://127.0.0.1:{state.local_port}/health",
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
        "--secret", required=True, help="Shared secret for auth",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=CONNECTOR_DEFAULT_PORT,
        help="Listen port",
    )
    args = parser.parse_args()
    server = ConnectorServer(args.secret, args.port)
    server.run()


if __name__ == "__main__":
    main()
