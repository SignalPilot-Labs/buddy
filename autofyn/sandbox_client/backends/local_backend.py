"""Local Docker sandbox backend — runs user-editable docker run command.

Executes the start command as a shell subprocess, parses AF_READY from
stdout (same protocol as remote sandboxes), and manages container
lifecycle via Docker CLI. The user sees and can edit the start command
in the dashboard — same UX as remote Docker and Slurm.
"""

import asyncio
import collections
import logging
import os

import docker
import docker.errors
from docker.models.containers import Container

from config.loader import sandbox_config
from db.constants import validate_host_mount
from sandbox_client.backends.base_backend import SandboxBackend
from sandbox_client.client import SandboxClient
from sandbox_client.models import SandboxInstance, SandboxStartError
from utils.constants import (
    AGENT_CONTAINER_NAME,
    DOCKER_SOCKET_PATH,
    ENV_KEY_ALLOW_DOCKER,
    ENV_KEY_IMAGE_TAG,
    SANDBOX_POOL_HEALTH_POLL_SEC,
    SANDBOX_POOL_IMAGE_BASE,
    SANDBOX_POOL_NETWORK,
)

log = logging.getLogger("sandbox_client.docker_local")

_RING_BUFFER_SIZE: int = 100
_STARTUP_TIMEOUT_SEC: int = 120

DEFAULT_DOCKER_START_CMD: str = (
    "docker run --rm=false"
    " --name autofyn-sandbox-$AF_RUN_KEY"
    " --hostname autofyn-sandbox-$AF_RUN_KEY"
    f" --network {SANDBOX_POOL_NETWORK}"
    " --cap-add SYS_PTRACE --cap-add SYS_ADMIN"
    " --security-opt apparmor:unconfined"
    " -v autofyn-repo-$AF_RUN_KEY:/home/agentuser/repo:rw"
    " $AF_HOST_MOUNTS"
    f" {SANDBOX_POOL_IMAGE_BASE}:$AF_IMAGE_TAG"
)


class DockerLocalBackend(SandboxBackend):
    """Local Docker via shell command — unified with remote sandboxes."""

    def __init__(self) -> None:
        """Initialize Docker client (for cleanup) and internal state."""
        self._docker = docker.from_env()
        self._containers: dict[str, str] = {}
        self._clients: dict[str, SandboxClient] = {}
        self._log_buffers: dict[str, collections.deque[str]] = {}
        self._log_tasks: dict[str, asyncio.Task[None]] = {}
        self._allow_docker = os.environ.get(ENV_KEY_ALLOW_DOCKER, "").lower() in (
            "1",
            "true",
            "yes",
        )
        cfg = sandbox_config()
        self._client_timeout: int = cfg["vm_timeout_sec"]
        self._health_timeout: int = cfg["health_timeout_sec"]
        self._image_tag: str = os.environ[ENV_KEY_IMAGE_TAG]
        log.info(
            "DockerLocalBackend image: %s:%s",
            SANDBOX_POOL_IMAGE_BASE,
            self._image_tag,
        )

    def _build_env(
        self,
        run_key: str,
        host_mounts: list[dict[str, str]] | None,
    ) -> dict[str, str]:
        """Build shell env vars for the start command subprocess."""
        mount_flags = self._compute_mount_flags(host_mounts)
        return {
            **os.environ,
            "AF_RUN_KEY": run_key,
            "AF_IMAGE_TAG": self._image_tag,
            "AF_HOST_MOUNTS": mount_flags,
        }

    def _compute_mount_flags(
        self,
        host_mounts: list[dict[str, str]] | None,
    ) -> str:
        """Build extra -v flags for Docker socket and host mounts."""
        parts: list[str] = []
        if self._allow_docker:
            parts.append(f"-v {DOCKER_SOCKET_PATH}:{DOCKER_SOCKET_PATH}:rw")
        if host_mounts:
            for mount in host_mounts:
                host_path = mount["host_path"]
                container_path = mount["container_path"]
                mode = mount.get("mode", "ro")
                error = validate_host_mount(host_path, container_path, mode)
                if error:
                    log.warning("Skipping invalid host mount: %s", error)
                    continue
                parts.append(f"-v {host_path}:{container_path}:{mode}")
                log.info("Host mount: %s -> %s (%s)", host_path, container_path, mode)
        return " ".join(parts)

    async def create(
        self,
        run_key: str,
        host_mounts: list[dict[str, str]] | None,
        start_cmd: str,
    ) -> tuple[SandboxInstance, list[dict]]:
        """Run the start command, parse AF_READY, return handle."""
        container_name = f"autofyn-sandbox-{run_key}"
        env = self._build_env(run_key, host_mounts)

        proc = await asyncio.create_subprocess_shell(
            start_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )

        ready_data = await self._wait_for_ready(proc, run_key, _STARTUP_TIMEOUT_SEC)
        ready_port: int = ready_data["port"]

        container_id = await self._get_container_id(container_name)
        self._containers[run_key] = container_id
        log.info("Started sandbox %s (%s) on port %d", container_name, container_id[:12], ready_port)

        self._start_log_drainer(run_key, proc)

        extracted_secret: str = ready_data["secret"]
        url = f"http://{container_name}:{ready_port}"

        try:
            await self._create_client(run_key, url)
        except Exception:
            self._containers.pop(run_key, None)
            self._log_buffers.pop(run_key, None)
            self._log_tasks.pop(run_key, None)
            self._clients.pop(run_key, None)
            await self._remove_container(container_id, container_name)
            await self._remove_volume(f"autofyn-repo-{run_key}")
            raise

        handle = SandboxInstance(
            run_key=run_key,
            url=url,
            sandbox_secret=extracted_secret,
            sandbox_id=None,
        )
        return handle, []

    async def _wait_for_ready(
        self,
        proc: asyncio.subprocess.Process,
        run_key: str,
        timeout: int,
    ) -> dict:
        """Read stdout lines until AF_READY marker or timeout."""
        buf: list[str] = []

        async def _read() -> dict:
            assert proc.stdout is not None
            async for line_bytes in proc.stdout:
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                buf.append(line)
                data = self.parse_ready_marker(line)
                if data is not None:
                    return data
            tail = "\n".join(buf[-10:]) if buf else "(no output)"
            raise SandboxStartError(
                f"Start command exited without AF_READY:\n{tail}",
                [],
            )

        try:
            return await asyncio.wait_for(_read(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            tail = "\n".join(buf[-10:]) if buf else "(no output)"
            raise SandboxStartError(
                f"Start command timed out after {timeout}s:\n{tail}",
                [],
            )

    async def _get_container_id(self, container_name: str) -> str:
        """Look up container ID by name via Docker API."""
        container: Container = await asyncio.to_thread(
            self._docker.containers.get, container_name
        )
        cid: str = container.id or ""
        return cid

    def _start_log_drainer(
        self,
        run_key: str,
        proc: asyncio.subprocess.Process,
    ) -> None:
        """Start async task draining remaining stdout into ring buffer."""
        ring: collections.deque[str] = collections.deque(maxlen=_RING_BUFFER_SIZE)
        self._log_buffers[run_key] = ring

        async def _drain() -> None:
            if proc.stdout is None:
                return
            try:
                async for line_bytes in proc.stdout:
                    line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                    ring.append(line)
            except Exception as exc:
                log.debug("Log drainer ended for %s: %s", run_key, exc)

        self._log_tasks[run_key] = asyncio.create_task(_drain())

    async def _create_client(
        self,
        run_key: str,
        url: str,
    ) -> None:
        """Create a SandboxClient and wait for health."""
        stale = self._clients.pop(run_key, None)
        if stale:
            await stale.close()
        client = SandboxClient(
            url,
            self._health_timeout,
            self._client_timeout,
            sandbox_secret=None,
            extra_headers=None,
        )
        self._clients[run_key] = client
        await self.wait_healthy(client, url, self._health_timeout, SANDBOX_POOL_HEALTH_POLL_SEC)

    async def destroy(self, handle: SandboxInstance) -> None:
        """Stop and remove a sandbox container + its volume."""
        await self._destroy_by_key(handle.run_key)

    def get_client(self, run_key: str) -> SandboxClient | None:
        """Return a cached SandboxClient for a live sandbox, or None."""
        return self._clients.get(run_key)

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

    async def get_sandbox_logs(
        self, run_key: str | None, tail: int
    ) -> list[str]:
        """Fetch logs from a sandbox container."""
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
        """Stop and remove container + volume by run key."""
        container_id = self._containers.pop(run_key, None)
        if not container_id:
            return
        container_name = f"autofyn-sandbox-{run_key}"
        volume_name = f"autofyn-repo-{run_key}"

        client = self._clients.pop(run_key, None)
        if client:
            await client.close()
        self._log_buffers.pop(run_key, None)
        task = self._log_tasks.pop(run_key, None)
        if task:
            task.cancel()

        await self._remove_container(container_id, container_name)
        await self._remove_volume(volume_name)

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
