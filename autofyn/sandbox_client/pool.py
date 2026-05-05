"""Sandbox pool — per-run backend factory.

Instantiated once by the agent server. Resolves which SandboxBackend
to use per run based on sandbox_id (None = local Docker, UUID = remote).
"""

import json
import logging
import os

import httpx

from db.constants import (
    REMOTE_SANDBOX_KEY_PREFIX,
    SANDBOX_TYPE_SLURM,
)
from sandbox_client.backend import SandboxBackend
from sandbox_client.base_remote import CONNECTOR_SECRET_HEADER
from sandbox_client.client import SandboxClient
from sandbox_client.docker_local import DockerLocalBackend
from sandbox_client.docker_remote import DockerRemoteBackend
from sandbox_client.instance import SandboxInstance
from sandbox_client.slurm_backend import SlurmBackend
from utils.constants import ENV_KEY_CONNECTOR_SECRET, ENV_KEY_CONNECTOR_URL
from utils.db import get_setting_value

log = logging.getLogger("sandbox_client.pool")


class SandboxPool:
    """Per-run backend factory. Agent code calls pool methods — doesn't know local vs remote."""

    def __init__(self) -> None:
        """Initialize the pool with a local Docker backend and connector env vars."""
        self._docker_local = DockerLocalBackend()
        self._handles: dict[str, SandboxInstance] = {}
        self._remote_backends: dict[str, SandboxBackend] = {}
        self._connector_url: str | None = os.environ.get(ENV_KEY_CONNECTOR_URL) or None
        self._connector_secret: str | None = os.environ.get(ENV_KEY_CONNECTOR_SECRET) or None

    async def create(
        self,
        run_key: str,
        health_timeout: int,
        extra_env: dict[str, str] | None,
        host_mounts: list[dict[str, str]] | None,
        sandbox_secret: str,
        sandbox_id: str | None,
        start_cmd: str | None,
    ) -> tuple[SandboxClient, list[dict]]:
        """Spin up a sandbox for a run. Returns (client, startup_events)."""
        backend = await self._resolve_backend(sandbox_id)
        handle, events = await backend.create(
            run_key, health_timeout, extra_env, host_mounts,
            sandbox_secret, start_cmd,
        )
        self._handles[run_key] = handle

        if sandbox_id is None:
            client = self._docker_local.get_client(run_key)
            if client is None:
                raise RuntimeError(f"No client available for run {run_key}")
            return client, events

        # Remote: point SandboxClient at the connector proxy URL
        client = SandboxClient(
            base_url=handle.url,
            health_timeout=health_timeout,
            timeout=health_timeout,
            sandbox_secret=handle.sandbox_secret,
            extra_headers=None,
        )
        return client, events

    async def destroy(self, run_key: str) -> None:
        """Stop and remove a sandbox. Closes cached client."""
        handle = self._handles.pop(run_key, None)
        if not handle:
            return
        backend = await self._resolve_backend(handle.sandbox_id)
        await backend.destroy(handle)

    async def destroy_all(self) -> None:
        """Tear down all managed sandboxes — remote first, then local Docker."""
        for run_key in list(self._handles.keys()):
            handle = self._handles.pop(run_key, None)
            if handle and handle.sandbox_id is not None:
                try:
                    backend = await self._resolve_backend(handle.sandbox_id)
                    await backend.destroy(handle)
                except Exception as exc:
                    log.error("Failed to destroy remote sandbox %s: %s", run_key, exc)
        await self._docker_local.destroy_all()

    def get_client(self, run_key: str) -> SandboxClient | None:
        """Return a cached SandboxClient for a live local sandbox, or None."""
        return self._docker_local.get_client(run_key)

    async def get_self_logs(self, tail: int) -> list[str]:
        """Fetch logs from the agent container itself."""
        return await self._docker_local.get_self_logs(tail)

    async def get_sandbox_logs(self, run_key: str | None, tail: int) -> list[str]:
        """Fetch logs from a sandbox container."""
        return await self._docker_local.get_sandbox_logs(run_key, tail)

    async def get_logs(self, run_key: str, tail: int) -> list[str]:
        """Fetch logs from the ring buffer for a run."""
        handle = self._handles.get(run_key)
        if not handle:
            return await self._docker_local.get_logs(run_key, tail)
        backend = await self._resolve_backend(handle.sandbox_id)
        return await backend.get_logs(run_key, tail)

    async def test_connection(self, sandbox_id: str) -> dict:
        """Test SSH connection and image availability for a remote sandbox."""
        if self._connector_url is None:
            raise RuntimeError("CONNECTOR_URL not set — cannot reach connector")
        if self._connector_secret is None:
            raise RuntimeError("CONNECTOR_SECRET not set — cannot reach connector")

        config_str = await get_setting_value(f"{REMOTE_SANDBOX_KEY_PREFIX}{sandbox_id}")
        if config_str is None:
            raise ValueError(f"No remote sandbox config found for sandbox_id={sandbox_id}")

        config: dict[str, str | int] = json.loads(config_str)
        headers = {CONNECTOR_SECRET_HEADER: self._connector_secret}
        body = {
            "ssh_target": str(config["ssh_target"]),
            "sandbox_type": str(config["type"]),
            "start_cmd": str(config["default_start_cmd"]),
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
                resp = await client.post(
                    f"{self._connector_url}/sandboxes/test",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                result: dict = resp.json()
                return result
        except httpx.ConnectError:
            raise RuntimeError("Connector not reachable — is it running? (autofyn start)")

    async def _resolve_backend(self, sandbox_id: str | None) -> SandboxBackend:
        """Resolve the backend for a given sandbox_id.

        Returns local Docker backend for None. For a remote UUID, reads the
        config from DB settings and instantiates the appropriate backend.
        Caches remote backends by sandbox_id to avoid repeated DB reads.
        """
        if sandbox_id is None:
            return self._docker_local

        cached = self._remote_backends.get(sandbox_id)
        if cached is not None:
            return cached

        if self._connector_url is None:
            raise RuntimeError(
                f"Remote sandbox {sandbox_id} requested but {ENV_KEY_CONNECTOR_URL} is not set"
            )
        if self._connector_secret is None:
            raise RuntimeError(
                f"Remote sandbox {sandbox_id} requested but {ENV_KEY_CONNECTOR_SECRET} is not set"
            )

        config_str = await get_setting_value(f"{REMOTE_SANDBOX_KEY_PREFIX}{sandbox_id}")
        if config_str is None:
            raise ValueError(f"No remote sandbox config found for sandbox_id={sandbox_id}")

        config: dict[str, str | int] = json.loads(config_str)
        sandbox_type: str = str(config["type"])
        ssh_target: str = str(config["ssh_target"])
        heartbeat_timeout: int = int(config["heartbeat_timeout"])

        backend: SandboxBackend
        if sandbox_type == SANDBOX_TYPE_SLURM:
            backend = SlurmBackend(
                connector_url=self._connector_url,
                connector_secret=self._connector_secret,
                sandbox_id=sandbox_id,
                ssh_target=ssh_target,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            backend = DockerRemoteBackend(
                connector_url=self._connector_url,
                connector_secret=self._connector_secret,
                sandbox_id=sandbox_id,
                ssh_target=ssh_target,
                heartbeat_timeout=heartbeat_timeout,
            )

        self._remote_backends[sandbox_id] = backend
        return backend
