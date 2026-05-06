"""Abstract base class for sandbox backends.

Defines the contract that all sandbox backends (local Docker, remote
Docker, remote Slurm) must implement. Common helpers for health polling
and AF_READY parsing live here — subclasses only differ in how they
execute the start command (local subprocess vs connector SSH).
"""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from sandbox_client.client import SandboxClient
from sandbox_client.models import SandboxInstance

log = logging.getLogger("sandbox_client.base_backend")

MARKER_RE: re.Pattern[str] = re.compile(r"(AF_READY)\s+(\{.*\})")


class SandboxBackend(ABC):
    """Base class for all sandbox backends."""

    @abstractmethod
    async def create(
        self,
        run_key: str,
        host_mounts: list[dict[str, str]] | None,
        start_cmd: str,
    ) -> tuple[SandboxInstance, list[dict]]:
        """Spin up a sandbox and return (handle, startup_events).

        Each backend owns its timeouts internally — the caller just
        provides run_key, mounts, and the start command.
        """
        ...

    @abstractmethod
    async def destroy(self, handle: SandboxInstance) -> None:
        """Stop and remove a sandbox."""
        ...

    @abstractmethod
    async def destroy_all(self) -> None:
        """Tear down all managed sandboxes."""
        ...

    @abstractmethod
    async def get_logs(self, run_key: str, tail: int) -> list[str]:
        """Fetch recent log lines from a sandbox."""
        ...

    @staticmethod
    def parse_ready_marker(line: str) -> dict[str, Any] | None:
        """Parse AF_READY JSON from a log line. Returns None if not a marker.

        Validates that the marker contains the required keys (host, port,
        secret). Raises ValueError if any are missing so callers get a clear
        error instead of a KeyError deep in sandbox setup.
        """
        match = MARKER_RE.search(line)
        if not match:
            return None
        data: dict[str, Any] = json.loads(match.group(2))
        missing = [k for k in ("host", "port", "secret") if k not in data]
        if missing:
            raise ValueError(
                f"AF_READY marker missing required keys {missing}: {line[:200]}"
            )
        return data

    @staticmethod
    async def wait_healthy(
        client: SandboxClient,
        name: str,
        timeout: int,
        poll_interval: int,
    ) -> None:
        """Poll sandbox /health until ready or timeout."""
        for _ in range(timeout // poll_interval + 1):
            try:
                await client.health()
                log.info("Sandbox %s healthy", name)
                return
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                ConnectionRefusedError,
            ):
                await asyncio.sleep(poll_interval)
        raise TimeoutError(f"Sandbox {name} not healthy after {timeout}s")
