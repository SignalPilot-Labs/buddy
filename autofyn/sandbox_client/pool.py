"""Sandbox container pool — spins up/tears down per-run sandbox containers.

The autofyn container has Docker socket access and manages sandbox lifecycle.
Each run gets an isolated sandbox with its own repo volume.
"""

import asyncio
import logging
import os

import docker
import httpx
import docker.errors
from docker.models.containers import Container

from db.constants import validate_host_mount
from utils.constants import (
    DOCKER_SOCKET_PATH,
    ENV_KEY_ALLOW_DOCKER,
    SANDBOX_POOL_ENV_PASSTHROUGH,
    SANDBOX_POOL_HEALTH_POLL_SEC,
    SANDBOX_POOL_IMAGE,
    SANDBOX_POOL_NETWORK,
    SANDBOX_POOL_PORT,
)
from sandbox_client.client import SandboxClient

log = logging.getLogger("sandbox_client.pool")

_PASSTHROUGH_ENV_VARS = SANDBOX_POOL_ENV_PASSTHROUGH


class SandboxPool:
    """Manages per-run sandbox containers via Docker API."""

    def __init__(self) -> None:
        self._docker = docker.from_env()
        self._containers: dict[str, str] = {}
        self._allow_docker = os.environ.get(ENV_KEY_ALLOW_DOCKER, "").lower() in ("1", "true", "yes")

    def _container_env(self) -> dict[str, str]:
        """Build env vars for pool-created sandbox containers.

        Passes auth tokens so the Claude SDK and git operations work inside
        the sandbox. These are stripped from subprocess env by _safe_env().
        """
        env: dict[str, str] = {"GIT_TERMINAL_PROMPT": "0"}
        for key in _PASSTHROUGH_ENV_VARS:
            val = os.environ.get(key, "")
            if val:
                env[key] = val
        return env

    async def create(
        self,
        run_key: str,
        health_timeout: int,
        extra_env: dict[str, str] | None,
        host_mounts: list[dict[str, str]] | None,
    ) -> SandboxClient:
        """Spin up a sandbox container for a run. Returns a connected SandboxClient."""
        container_name = f"autofyn-sandbox-{run_key}"
        volume_name = f"autofyn-repo-{run_key}"

        env = self._container_env()
        if extra_env is not None:
            env.update(extra_env)

        volumes: dict[str, dict[str, str]] = {
            volume_name: {"bind": "/home/agentuser/repo", "mode": "rw"},
        }
        if self._allow_docker:
            volumes[DOCKER_SOCKET_PATH] = {"bind": DOCKER_SOCKET_PATH, "mode": "rw"}
            log.warning("Docker socket mounted into sandbox %s (--allow-docker)", container_name)
        if host_mounts:
            for mount in host_mounts:
                host_path = mount.get("host_path", "")
                container_path = mount.get("container_path", "")
                mode = mount.get("mode", "ro")  # default read-only
                error = validate_host_mount(host_path, container_path, mode)
                if error:
                    log.warning("Skipping invalid host mount: %s", error)
                    continue
                volumes[host_path] = {"bind": container_path, "mode": mode}
                log.info("Host mount: %s → %s (%s)", host_path, container_path, mode)

        container: Container = await asyncio.to_thread(
            self._docker.containers.run,
            image=SANDBOX_POOL_IMAGE,
            name=container_name,
            hostname=container_name,
            detach=True,
            remove=False,
            network=SANDBOX_POOL_NETWORK,
            volumes=volumes,
            # gVisor requires these capabilities
            cap_add=["SYS_PTRACE", "SYS_ADMIN"],
            security_opt=["apparmor:unconfined"],
            environment=env,
        )
        self._containers[run_key] = container.id or ""
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

        await self._remove_container(container_id, container_name)
        await self._remove_volume(volume_name)

    async def get_logs(self, run_key: str | None, tail: int) -> list[str]:
        """Fetch logs from a sandbox container. Falls back to static sandbox."""
        if run_key and run_key in self._containers:
            container_name = f"autofyn-sandbox-{run_key}"
        elif self._containers:
            first_key = next(iter(self._containers))
            container_name = f"autofyn-sandbox-{first_key}"
        else:
            container_name = "autofyn-sandbox"

        try:
            container = self._docker.containers.get(container_name)
            raw: bytes = await asyncio.to_thread(container.logs, tail=tail, timestamps=True)
            return raw.decode("utf-8", errors="replace").splitlines()
        except docker.errors.NotFound:
            return []

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
        """Poll sandbox health until ready or timeout."""
        for _ in range(timeout // SANDBOX_POOL_HEALTH_POLL_SEC + 1):
            try:
                await client.health()
                log.info("Sandbox %s healthy", name)
                return
            except (httpx.ConnectError, httpx.TimeoutException, ConnectionRefusedError):
                await asyncio.sleep(SANDBOX_POOL_HEALTH_POLL_SEC)
        raise TimeoutError(f"Sandbox {name} not healthy after {timeout}s")

    async def _remove_container(self, container_id: str, name: str) -> None:
        """Remove a container by id. No-op if already gone."""
        try:
            container = self._docker.containers.get(container_id)
            await asyncio.to_thread(container.remove, force=True)
            log.info("Removed sandbox %s", name)
        except docker.errors.NotFound:
            log.debug("Sandbox %s already removed", name)

    async def _remove_volume(self, volume_name: str) -> None:
        """Remove a volume. No-op if already gone."""
        try:
            vol = self._docker.volumes.get(volume_name)
            await asyncio.to_thread(vol.remove, force=True)
            log.info("Removed volume %s", volume_name)
        except docker.errors.NotFound:
            log.debug("Volume %s already removed", volume_name)
