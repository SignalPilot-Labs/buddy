"""Sandbox container pool — spins up/tears down per-run sandbox containers.

The autofyn container has Docker socket access and manages sandbox lifecycle.
Each run gets an isolated sandbox with its own repo volume.
"""

import asyncio
import logging

import docker
from docker.models.containers import Container

from utils.constants import (
    SANDBOX_POOL_HEALTH_POLL_SEC,
    SANDBOX_POOL_IMAGE,
    SANDBOX_POOL_NETWORK,
    SANDBOX_POOL_PORT,
)
from sandbox_manager.client import SandboxClient

log = logging.getLogger("sandbox_manager.pool")


class SandboxPool:
    """Manages per-run sandbox containers via Docker API."""

    def __init__(self) -> None:
        self._docker = docker.from_env()
        self._containers: dict[str, str] = {}  # run_key -> container_id

    async def create(self, run_key: str, health_timeout: int) -> SandboxClient:
        """Spin up a sandbox container for a run. Returns a connected SandboxClient."""
        container_name = f"autofyn-sandbox-{run_key}"
        volume_name = f"autofyn-repo-{run_key}"

        container: Container = await asyncio.to_thread(
            self._docker.containers.run,
            image=SANDBOX_POOL_IMAGE,
            name=container_name,
            hostname=container_name,
            detach=True,
            remove=False,
            network=SANDBOX_POOL_NETWORK,
            volumes={volume_name: {"bind": "/home/agentuser/repo", "mode": "rw"}},
            cap_add=["SYS_PTRACE", "SYS_ADMIN"],
            security_opt=["apparmor:unconfined"],
            environment={"GIT_TERMINAL_PROMPT": "0"},
        )
        self._containers[run_key] = container.id or "Unknown"
        log.info("Started sandbox %s (%s)", container_name, container.short_id)

        url = f"http://{container_name}:{SANDBOX_POOL_PORT}"
        client = SandboxClient(url, health_timeout)
        await self._wait_healthy(client, container_name, health_timeout)
        return client

    async def destroy(self, run_key: str) -> None:
        """Stop and remove a sandbox container + its volume."""
        container_id = self._containers.pop(run_key, None)
        if not container_id:
            return
        container_name = f"autofyn-sandbox-{run_key}"
        volume_name = f"autofyn-repo-{run_key}"
        try:
            container = self._docker.containers.get(container_id)
            await asyncio.to_thread(container.remove, force=True)
            log.info("Removed sandbox %s", container_name)
        except Exception as e:
            log.warning("Failed to remove sandbox %s: %s", container_name, e)
        try:
            vol = self._docker.volumes.get(volume_name)
            await asyncio.to_thread(vol.remove, force=True)
            log.info("Removed volume %s", volume_name)
        except Exception as e:
            log.debug("Volume cleanup %s: %s", volume_name, e)

    async def destroy_all(self) -> None:
        """Tear down all managed sandbox containers."""
        keys = list(self._containers.keys())
        for key in keys:
            await self.destroy(key)

    async def _wait_healthy(
        self,
        client: SandboxClient,
        name: str,
        timeout: int,
    ) -> None:
        """Poll sandbox health until ready."""
        for _ in range(timeout // SANDBOX_POOL_HEALTH_POLL_SEC + 1):
            try:
                await client.health()
                log.info("Sandbox %s healthy", name)
                return
            except Exception:
                await asyncio.sleep(SANDBOX_POOL_HEALTH_POLL_SEC)
        raise TimeoutError(f"Sandbox {name} not healthy after {timeout}s")
