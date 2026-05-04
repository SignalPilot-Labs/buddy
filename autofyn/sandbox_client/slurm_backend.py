"""Slurm sandbox backend — runs sandboxes on HPC clusters via connector.

Uses SSH + srun/sbatch through the connector. Stop is derived from context:
srun = kill the start SSH process, sbatch = scancel <backend_id>.
"""

import logging

from sandbox_client.backend import SandboxBackend
from sandbox_client.handle import SandboxHandle
from sandbox_client.remote_mixin import RemoteBackendMixin

log = logging.getLogger("sandbox_client.slurm_backend")


class SlurmBackend(RemoteBackendMixin, SandboxBackend):
    """Remote Slurm via connector."""

    def __init__(
        self,
        connector_url: str,
        connector_secret: str,
        sandbox_id: str,
        ssh_target: str,
        heartbeat_timeout: int,
    ) -> None:
        RemoteBackendMixin.__init__(
            self,
            connector_url=connector_url,
            connector_secret=connector_secret,
            sandbox_id=sandbox_id,
            ssh_target=ssh_target,
            sandbox_type="slurm",
            heartbeat_timeout=heartbeat_timeout,
        )
        self._handles: dict[str, SandboxHandle] = {}

    async def create(
        self,
        run_key: str,
        health_timeout: int,
        extra_env: dict[str, str] | None,
        host_mounts: list[dict[str, str]] | None,
        sandbox_secret: str,
    ) -> SandboxHandle:
        """Start a Slurm sandbox via the connector."""
        raise NotImplementedError(
            "SlurmBackend.create requires start_cmd — use SandboxPool.create_remote()"
        )

    async def create_with_cmd(
        self,
        run_key: str,
        start_cmd: str,
        health_timeout: int,
        host_mounts: list[dict[str, str]] | None,
        sandbox_secret: str,
    ) -> tuple[SandboxHandle, list[dict]]:
        """Start a Slurm sandbox with an explicit start command.

        Returns (handle, events) where events is the list of NDJSON events
        consumed during startup. The caller (pool) persists these to the DB.
        """
        events: list[dict] = []
        host: str | None = None
        port: int | None = None
        backend_id: str | None = None

        async for event in self._start_remote_sandbox(
            run_key, start_cmd, sandbox_secret, host_mounts,
        ):
            events.append(event)
            etype = event.get("event")
            if etype == "queued":
                backend_id = event.get("backend_id")
            elif etype == "ready":
                host = event["host"]
                port = event["port"]
                if "backend_id" in event and backend_id is None:
                    backend_id = event["backend_id"]
            elif etype == "failed":
                raise RuntimeError(
                    f"Sandbox start failed: {event.get('error', 'unknown')}"
                )

        if host is None or port is None:
            raise RuntimeError("Sandbox start did not emit AF_READY marker")

        url = self._build_proxy_url(run_key)
        handle = SandboxHandle(
            run_key=run_key,
            url=url,
            backend_id=backend_id,
            sandbox_secret=sandbox_secret,
            sandbox_id=self._sandbox_id,
            sandbox_type="slurm",
            remote_host=host,
            remote_port=port,
        )
        self._handles[run_key] = handle
        return handle, events

    async def destroy(self, handle: SandboxHandle) -> None:
        """Stop a Slurm sandbox via the connector."""
        self._handles.pop(handle.run_key, None)
        await self._stop_remote_sandbox(handle.run_key)

    async def destroy_all(self) -> None:
        """Tear down all managed Slurm sandboxes."""
        keys = list(self._handles.keys())
        for key in keys:
            handle = self._handles.pop(key, None)
            if handle:
                await self._stop_remote_sandbox(key)

    async def get_logs(self, run_key: str, tail: int) -> list[str]:
        """Fetch logs from the connector ring buffer."""
        return await self._get_connector_logs(run_key, tail)
