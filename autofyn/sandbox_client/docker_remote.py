"""Remote Docker sandbox backend — runs sandboxes on remote machines via connector.

Uses SSH + docker run through the connector. Stop is `docker rm -f <backend_id>`.
Logs use `docker logs` over SSH (container survives crashes).
"""

import logging

from sandbox_client.backend import SandboxBackend
from sandbox_client.instance import SandboxInstance
from sandbox_client.base_remote import BaseRemoteBackend

log = logging.getLogger("sandbox_client.docker_remote")


class DockerRemoteBackend(BaseRemoteBackend, SandboxBackend):
    """Remote Docker via connector."""

    def __init__(
        self,
        connector_url: str,
        connector_secret: str,
        sandbox_id: str,
        ssh_target: str,
        heartbeat_timeout: int,
    ) -> None:
        BaseRemoteBackend.__init__(
            self,
            connector_url=connector_url,
            connector_secret=connector_secret,
            sandbox_id=sandbox_id,
            ssh_target=ssh_target,
            sandbox_type="docker",
            heartbeat_timeout=heartbeat_timeout,
        )
        self._handles: dict[str, SandboxInstance] = {}

    async def create(
        self,
        run_key: str,
        health_timeout: int,
        extra_env: dict[str, str] | None,
        host_mounts: list[dict[str, str]] | None,
        sandbox_secret: str,
    ) -> SandboxInstance:
        """Start a remote Docker sandbox via the connector."""
        raise NotImplementedError(
            "DockerRemoteBackend.create requires start_cmd"
            " — use SandboxPool.create_remote()"
        )

    async def create_with_cmd(
        self,
        run_key: str,
        start_cmd: str,
        health_timeout: int,
        host_mounts: list[dict[str, str]] | None,
        sandbox_secret: str,
    ) -> tuple[SandboxInstance, list[dict]]:
        """Start a remote Docker sandbox with an explicit start command.

        Returns (handle, events) for caller persistence.
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
        handle = SandboxInstance(
            run_key=run_key,
            url=url,
            backend_id=backend_id,
            sandbox_secret=sandbox_secret,
            sandbox_id=self._sandbox_id,
            sandbox_type="docker",
            remote_host=host,
            remote_port=port,
        )
        self._handles[run_key] = handle
        return handle, events

    async def destroy(self, handle: SandboxInstance) -> None:
        """Stop a remote Docker sandbox via the connector."""
        self._handles.pop(handle.run_key, None)
        await self._stop_remote_sandbox(handle.run_key)

    async def destroy_all(self) -> None:
        """Tear down all managed remote Docker sandboxes."""
        keys = list(self._handles.keys())
        for key in keys:
            handle = self._handles.pop(key, None)
            if handle:
                await self._stop_remote_sandbox(key)

    async def get_logs(self, run_key: str, tail: int) -> list[str]:
        """Fetch logs via docker logs over SSH (container survives crashes)."""
        return await self._get_connector_logs(run_key, tail)
