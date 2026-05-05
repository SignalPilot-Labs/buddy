"""Shared transport logic for remote sandbox backends.

Both SlurmBackend and DockerRemoteBackend use the connector for SSH tunnels,
NDJSON streaming, and reverse proxying. This base class holds the common HTTP
calls to the connector and the shared create/destroy lifecycle.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from db.constants import SANDBOX_QUEUE_TIMEOUT_SEC, SSH_CONNECT_TIMEOUT_SEC
from sandbox_client.backend import SandboxBackend
from sandbox_client.errors import SandboxStartError
from sandbox_client.instance import SandboxInstance
from utils.db_logging import log_audit

log = logging.getLogger("sandbox_client.base_remote")

CONNECTOR_SECRET_HEADER: str = "X-Connector-Secret"


class BaseRemoteBackend(SandboxBackend):
    """Shared connector transport and lifecycle for remote backends."""

    def __init__(
        self,
        connector_url: str,
        connector_secret: str,
        sandbox_id: str,
        ssh_target: str,
        sandbox_type: str,
        heartbeat_timeout: int,
    ) -> None:
        """Initialize the remote backend with connector connection details."""
        self._connector_url = connector_url
        self._connector_secret = connector_secret
        self._sandbox_id = sandbox_id
        self._ssh_target = ssh_target
        self._sandbox_type = sandbox_type
        self._heartbeat_timeout = heartbeat_timeout
        self._handles: dict[str, SandboxInstance] = {}

    def _connector_headers(self) -> dict[str, str]:
        """Build headers for connector requests."""
        return {CONNECTOR_SECRET_HEADER: self._connector_secret}

    async def _start_remote_sandbox(
        self,
        run_key: str,
        start_cmd: str,
        sandbox_secret: str,
        host_mounts: list[dict[str, str]] | None,
        extra_env: dict[str, str] | None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """POST /sandboxes/start to connector, yield NDJSON events."""
        body: dict[str, Any] = {
            "run_key": run_key,
            "ssh_target": self._ssh_target,
            "start_cmd": start_cmd,
            "sandbox_type": self._sandbox_type,
            "sandbox_secret": sandbox_secret,
            "host_mounts": host_mounts or [],
            "heartbeat_timeout": self._heartbeat_timeout,
            "extra_env": extra_env or {},
        }
        timeout = httpx.Timeout(SANDBOX_QUEUE_TIMEOUT_SEC)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self._connector_url}/sandboxes/start",
                json=body,
                headers=self._connector_headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    event: dict[str, Any] = json.loads(stripped)
                    yield event

    async def _stop_remote_sandbox(self, run_key: str) -> None:
        """POST /sandboxes/stop to connector."""
        timeout = httpx.Timeout(SSH_CONNECT_TIMEOUT_SEC)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self._connector_url}/sandboxes/stop",
                json={"run_key": run_key},
                headers=self._connector_headers(),
            )
            resp.raise_for_status()

    async def _get_connector_logs(self, run_key: str, tail: int) -> list[str]:
        """GET /sandboxes/{run_key}/logs from connector ring buffer."""
        timeout = httpx.Timeout(SSH_CONNECT_TIMEOUT_SEC)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{self._connector_url}/sandboxes/{run_key}/logs",
                params={"tail": tail},
                headers=self._connector_headers(),
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            lines: list[str] = data["lines"]
            return lines

    def _build_proxy_url(self, run_key: str) -> str:
        """Build the reverse proxy URL for agent HTTP calls."""
        return f"{self._connector_url}/sandboxes/{run_key}"

    async def create(
        self,
        run_key: str,
        health_timeout: int,
        extra_env: dict[str, str] | None,
        host_mounts: list[dict[str, str]] | None,
        sandbox_secret: str,
        start_cmd: str | None,
    ) -> tuple[SandboxInstance, list[dict]]:
        """Start a remote sandbox via the connector.

        Streams NDJSON events and returns (handle, events).
        """
        if start_cmd is None:
            raise ValueError(
                f"{type(self).__name__}.create requires start_cmd for remote sandboxes"
            )

        events: list[dict[str, Any]] = []
        host: str | None = None
        port: int | None = None
        backend_id: str | None = None

        async for event in self._start_remote_sandbox(
            run_key, start_cmd, sandbox_secret, host_mounts, extra_env,
        ):
            events.append(event)
            etype = event.get("event")
            if etype == "queued":
                backend_id = event.get("backend_id")
                await log_audit(run_key, "sandbox_queued", {"backend_id": backend_id})
            elif etype == "status":
                await log_audit(run_key, "startup_log", {"line": event.get("message", "")})
            elif etype == "log":
                await log_audit(run_key, "startup_log", {"line": event.get("line", "")})
            elif etype == "ready":
                host = event["host"]
                port = event["port"]
                if "backend_id" in event and backend_id is None:
                    backend_id = event["backend_id"]
            elif etype == "failed":
                raise SandboxStartError(
                    f"Sandbox start failed: {event.get('error', 'unknown')}",
                    events,
                )

        if host is None or port is None:
            log_lines = [e["line"] for e in events if e.get("event") == "log"]
            tail = "\n".join(log_lines[-10:]) if log_lines else "(no output)"
            raise SandboxStartError(
                f"Start command exited without AF_READY:\n{tail}",
                events,
            )

        url = self._build_proxy_url(run_key)
        handle = SandboxInstance(
            run_key=run_key,
            url=url,
            backend_id=backend_id,
            sandbox_secret=sandbox_secret,
            sandbox_id=self._sandbox_id,
            sandbox_type=self._sandbox_type,
            remote_host=host,
            remote_port=port,
        )
        self._handles[run_key] = handle
        return handle, events

    async def destroy(self, handle: SandboxInstance) -> None:
        """Stop a remote sandbox via the connector."""
        self._handles.pop(handle.run_key, None)
        await self._stop_remote_sandbox(handle.run_key)

    async def destroy_all(self) -> None:
        """Tear down all managed remote sandboxes."""
        keys = list(self._handles.keys())
        for key in keys:
            handle = self._handles.pop(key, None)
            if handle:
                try:
                    await self._stop_remote_sandbox(key)
                except Exception as exc:
                    log.error("Failed to stop sandbox %s: %s", key, exc)

    async def get_logs(self, run_key: str, tail: int) -> list[str]:
        """Fetch logs from the connector ring buffer."""
        return await self._get_connector_logs(run_key, tail)
