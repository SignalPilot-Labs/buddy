"""Sandbox pool — per-run backend factory.

Instantiated once by the agent server. Resolves which SandboxBackend
to use per run based on sandbox_id (None = local Docker, UUID = remote).
"""

import logging

from sandbox_client.backend import SandboxBackend
from sandbox_client.client import SandboxClient
from sandbox_client.docker_local import DockerLocalBackend
from sandbox_client.instance import SandboxInstance

log = logging.getLogger("sandbox_client.pool")


class SandboxPool:
    """Per-run backend factory. Agent code calls pool methods — doesn't know local vs remote."""

    def __init__(self) -> None:
        """Initialize the pool with a local Docker backend."""
        self._docker_local = DockerLocalBackend()
        self._handles: dict[str, SandboxInstance] = {}

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
        backend = self._resolve_backend(sandbox_id)
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

        # Remote backends: client is constructed by the caller using the proxy URL
        raise NotImplementedError("Remote client construction not yet wired")

    async def destroy(self, run_key: str) -> None:
        """Stop and remove a sandbox. Closes cached client."""
        handle = self._handles.pop(run_key, None)
        if not handle:
            return
        backend = self._resolve_backend(handle.sandbox_id)
        await backend.destroy(handle)

    async def destroy_all(self) -> None:
        """Tear down all managed sandboxes."""
        await self._docker_local.destroy_all()
        self._handles.clear()

    def get_client(self, run_key: str) -> SandboxClient | None:
        """Return a cached SandboxClient for a live sandbox, or None."""
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
        backend = self._resolve_backend(handle.sandbox_id)
        return await backend.get_logs(run_key, tail)

    def _resolve_backend(self, sandbox_id: str | None) -> SandboxBackend:
        """Resolve the backend for a given sandbox_id."""
        if sandbox_id is None:
            return self._docker_local
        # Remote backends will be added in Phase 1c
        raise NotImplementedError(
            f"Remote sandbox backend not yet implemented for sandbox_id={sandbox_id}"
        )
