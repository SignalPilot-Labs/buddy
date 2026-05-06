"""Local Docker sandbox backend — manages per-run containers via Docker API.

Extracts the container lifecycle logic from the original SandboxManager into
a SandboxBackend subclass. Each run gets an isolated container with its own
repo volume. A ring buffer captures the last 100 lines of container stdout
for crash log retrieval.
"""

import asyncio
import collections
import logging
import os
import threading

import docker
import docker.errors
import httpx
from docker.models.containers import Container

from config.loader import sandbox_config
from db.constants import validate_host_mount
from sandbox_client.backends.base_backend import SandboxBackend
from sandbox_client.client import SandboxClient
from sandbox_client.models import SandboxInstance
from utils.constants import (
    AGENT_CONTAINER_NAME,
    DOCKER_SOCKET_PATH,
    ENV_KEY_ALLOW_DOCKER,
    ENV_KEY_IMAGE_TAG,
    ENV_KEY_SANDBOX_SECRET,
    SANDBOX_POOL_ENV_PASSTHROUGH,
    SANDBOX_POOL_HEALTH_POLL_SEC,
    SANDBOX_POOL_IMAGE_BASE,
    SANDBOX_POOL_NETWORK,
    SANDBOX_POOL_PORT,
)

log = logging.getLogger("sandbox_client.docker_local")

_RING_BUFFER_SIZE: int = 100


class _LogDrainer(threading.Thread):
    """Background thread that drains container stdout into a ring buffer."""

    def __init__(self, container: Container, buffer: collections.deque[str]) -> None:
        """Initialize the log drainer with a container and ring buffer."""
        super().__init__(daemon=True)
        self._container = container
        self._buffer = buffer

    def run(self) -> None:
        """Read container logs line by line into the ring buffer."""
        try:
            for line in self._container.logs(stream=True, follow=True):
                decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                self._buffer.append(decoded)
        except Exception as exc:
            log.debug("Log drainer ended: %s", exc)


class DockerLocalBackend(SandboxBackend):
    """Local Docker via Docker API — existing behavior extracted from SandboxManager."""

    def __init__(self) -> None:
        """Initialize Docker client and internal state."""
        self._docker = docker.from_env()
        self._containers: dict[str, str] = {}
        self._clients: dict[str, SandboxClient] = {}
        self._log_buffers: dict[str, collections.deque[str]] = {}
        self._log_drainers: dict[str, _LogDrainer] = {}
        self._allow_docker = os.environ.get(ENV_KEY_ALLOW_DOCKER, "").lower() in (
            "1",
            "true",
            "yes",
        )
        self._client_timeout: int = sandbox_config()["vm_timeout_sec"]
        self._sandbox_secret: str = os.environ[ENV_KEY_SANDBOX_SECRET]
        self._image = f"{SANDBOX_POOL_IMAGE_BASE}:{os.environ[ENV_KEY_IMAGE_TAG]}"
        log.info("DockerLocalBackend image: %s", self._image)

    def _container_env(self) -> dict[str, str]:
        """Build env vars for pool-created sandbox containers."""
        env: dict[str, str] = {"GIT_TERMINAL_PROMPT": "0"}
        for key in SANDBOX_POOL_ENV_PASSTHROUGH:
            val = os.environ.get(key, "")
            if val:
                env[key] = val
        return env

    async def create(
        self,
        run_key: str,
        health_timeout: int,
        host_mounts: list[dict[str, str]] | None,
        start_cmd: str | None,
    ) -> tuple[SandboxInstance, list[dict]]:
        """Spin up a sandbox container for a run. Returns (handle, [])."""
        container_name = f"autofyn-sandbox-{run_key}"
        volume_name = f"autofyn-repo-{run_key}"

        env = self._container_env()

        volumes = self._build_volumes(volume_name, host_mounts)

        container: Container = await asyncio.to_thread(
            self._docker.containers.run,
            image=self._image,
            name=container_name,
            hostname=container_name,
            detach=True,
            remove=False,
            network=SANDBOX_POOL_NETWORK,
            volumes=volumes,
            cap_add=["SYS_PTRACE", "SYS_ADMIN"],
            security_opt=["apparmor:unconfined"],
            environment=env,
        )
        container_id = container.id or ""
        self._containers[run_key] = container_id
        log.info("Started sandbox %s (%s)", container_name, container.short_id)

        self._start_log_drainer(run_key, container)
        try:
            await self._replace_client(run_key, container_name, health_timeout)
        except Exception:
            self._containers.pop(run_key, None)
            self._log_buffers.pop(run_key, None)
            self._log_drainers.pop(run_key, None)
            self._clients.pop(run_key, None)
            await self._remove_container(container_id, container_name)
            await self._remove_volume(volume_name)
            raise

        handle = SandboxInstance(
            run_key=run_key,
            url=f"http://{container_name}:{SANDBOX_POOL_PORT}",
            sandbox_secret=self._sandbox_secret,
            sandbox_id=None,
        )
        return handle, []

    def _start_log_drainer(self, run_key: str, container: Container) -> None:
        """Start a background log drainer for a container."""
        buf: collections.deque[str] = collections.deque(maxlen=_RING_BUFFER_SIZE)
        self._log_buffers[run_key] = buf
        drainer = _LogDrainer(container, buf)
        self._log_drainers[run_key] = drainer
        drainer.start()

    async def _replace_client(
        self,
        run_key: str,
        container_name: str,
        health_timeout: int,
    ) -> None:
        """Close any stale client and create a new one, waiting for health."""
        stale_client = self._clients.pop(run_key, None)
        if stale_client:
            await stale_client.close()

        url = f"http://{container_name}:{SANDBOX_POOL_PORT}"
        client = SandboxClient(url, health_timeout, self._client_timeout, sandbox_secret=None, extra_headers=None)
        self._clients[run_key] = client
        await self._wait_healthy(client, container_name, health_timeout)

    def _build_volumes(
        self,
        volume_name: str,
        host_mounts: list[dict[str, str]] | None,
    ) -> dict[str, dict[str, str]]:
        """Build the volumes dict for container creation."""
        volumes: dict[str, dict[str, str]] = {
            volume_name: {"bind": "/home/agentuser/repo", "mode": "rw"},
        }
        if self._allow_docker:
            volumes[DOCKER_SOCKET_PATH] = {"bind": DOCKER_SOCKET_PATH, "mode": "rw"}
        if host_mounts:
            for mount in host_mounts:
                self._add_host_mount(volumes, mount)
        return volumes

    def _add_host_mount(
        self,
        volumes: dict[str, dict[str, str]],
        mount: dict[str, str],
    ) -> None:
        """Validate and add a single host mount to the volumes dict."""
        host_path = mount["host_path"]
        container_path = mount["container_path"]
        mode = mount.get("mode", "ro")
        error = validate_host_mount(host_path, container_path, mode)
        if error:
            log.warning("Skipping invalid host mount: %s", error)
            return
        volumes[host_path] = {"bind": container_path, "mode": mode}
        log.info("Host mount: %s -> %s (%s)", host_path, container_path, mode)

    async def destroy(self, handle: SandboxInstance) -> None:
        """Stop and remove a sandbox container + its volume."""
        await self._destroy_by_key(handle.run_key)

    def get_client(self, run_key: str) -> SandboxClient | None:
        """Return a cached SandboxClient for a live sandbox, or None."""
        if run_key not in self._containers:
            return None
        if run_key in self._clients:
            return self._clients[run_key]
        log.warning(
            "run_key %s is in _containers but has no cached client — state inconsistency",
            run_key,
        )
        return None

    async def get_logs(self, run_key: str, tail: int) -> list[str]:
        """Return last N lines from the ring buffer."""
        buf = self._log_buffers.get(run_key)
        if not buf:
            return []
        lines = list(buf)
        return lines[-tail:] if tail < len(lines) else lines

    async def get_self_logs(self, tail: int) -> list[str]:
        """Fetch logs from the agent container itself."""
        try:
            container = self._docker.containers.get(AGENT_CONTAINER_NAME)
            raw: bytes = await asyncio.to_thread(
                container.logs, tail=tail, timestamps=True
            )
            return raw.decode("utf-8", errors="replace").splitlines()
        except docker.errors.NotFound:
            return []

    async def get_sandbox_logs(self, run_key: str | None, tail: int) -> list[str]:
        """Fetch logs from a sandbox container (legacy API)."""
        container_name = self._resolve_sandbox_name(run_key)
        try:
            container = self._docker.containers.get(container_name)
            raw: bytes = await asyncio.to_thread(
                container.logs, tail=tail, timestamps=True
            )
            return raw.decode("utf-8", errors="replace").splitlines()
        except docker.errors.NotFound:
            return []

    def _resolve_sandbox_name(self, run_key: str | None) -> str:
        """Resolve a sandbox container name from a run key."""
        if run_key and run_key in self._containers:
            return f"autofyn-sandbox-{run_key}"
        if self._containers:
            first_key = next(iter(self._containers))
            return f"autofyn-sandbox-{first_key}"
        return "autofyn-sandbox"

    async def destroy_all(self) -> None:
        """Tear down all managed sandbox containers."""
        keys = list(self._containers.keys())
        for key in keys:
            await self._destroy_by_key(key)

    async def _destroy_by_key(self, run_key: str) -> None:
        """Internal destroy using run_key directly (no SandboxInstance needed)."""
        container_id = self._containers.pop(run_key, None)
        if not container_id:
            return
        container_name = f"autofyn-sandbox-{run_key}"
        volume_name = f"autofyn-repo-{run_key}"

        client = self._clients.pop(run_key, None)
        if client:
            await client.close()
        self._log_buffers.pop(run_key, None)
        self._log_drainers.pop(run_key, None)

        await self._remove_container(container_id, container_name)
        await self._remove_volume(volume_name)

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
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                ConnectionRefusedError,
            ):
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
