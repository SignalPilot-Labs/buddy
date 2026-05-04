"""Shared transport logic for remote sandbox backends.

Both SlurmBackend and DockerRemoteBackend use the connector for SSH tunnels,
NDJSON streaming, and reverse proxying. This mixin holds the common HTTP
calls to the connector.
"""

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from db.constants import SANDBOX_QUEUE_TIMEOUT_SEC, SSH_CONNECT_TIMEOUT_SEC

log = logging.getLogger("sandbox_client.base_remote")

CONNECTOR_SECRET_HEADER: str = "X-Connector-Secret"
NDJSON_CONTENT_TYPE: str = "application/x-ndjson"


class BaseRemoteBackend:
    """Shared connector transport for remote backends."""

    def __init__(
        self,
        connector_url: str,
        connector_secret: str,
        sandbox_id: str,
        ssh_target: str,
        sandbox_type: str,
        heartbeat_timeout: int,
    ) -> None:
        self._connector_url = connector_url
        self._connector_secret = connector_secret
        self._sandbox_id = sandbox_id
        self._ssh_target = ssh_target
        self._sandbox_type = sandbox_type
        self._heartbeat_timeout = heartbeat_timeout

    def _connector_headers(self) -> dict[str, str]:
        """Build headers for connector requests."""
        return {CONNECTOR_SECRET_HEADER: self._connector_secret}

    async def _start_remote_sandbox(
        self,
        run_key: str,
        start_cmd: str,
        sandbox_secret: str,
        host_mounts: list[dict[str, str]] | None,
    ) -> AsyncGenerator[dict, None]:
        """POST /sandboxes/start to connector, yield NDJSON events."""
        body: dict = {
            "run_key": run_key,
            "ssh_target": self._ssh_target,
            "start_cmd": start_cmd,
            "sandbox_type": self._sandbox_type,
            "sandbox_secret": sandbox_secret,
            "host_mounts": host_mounts or [],
            "heartbeat_timeout": self._heartbeat_timeout,
        }
        timeout = httpx.Timeout(SANDBOX_QUEUE_TIMEOUT_SEC)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self._connector_url}/sandboxes/start",
                json=body,
                headers=self._connector_headers(),
            ) as response:
                async for line in response.aiter_lines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    event: dict = json.loads(stripped)
                    yield event

    async def _stop_remote_sandbox(self, run_key: str) -> None:
        """POST /sandboxes/stop to connector."""
        timeout = httpx.Timeout(SSH_CONNECT_TIMEOUT_SEC)
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.post(
                f"{self._connector_url}/sandboxes/stop",
                json={"run_key": run_key},
                headers=self._connector_headers(),
            )

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
            data: dict = resp.json()
            lines: list[str] = data["lines"]
            return lines

    def _build_proxy_url(self, run_key: str) -> str:
        """Build the reverse proxy URL for agent HTTP calls."""
        return f"{self._connector_url}/sandboxes/{run_key}"
