"""Abstract base class for sandbox backends.

The agent calls backend.create() / backend.destroy() without knowing
whether the sandbox is a local Docker container or a remote Slurm job.
"""

from abc import ABC, abstractmethod

from sandbox_client.instance import SandboxInstance


class SandboxBackend(ABC):
    """Base class for all sandbox backends."""

    @abstractmethod
    async def create(
        self,
        run_key: str,
        health_timeout: int,
        extra_env: dict[str, str] | None,
        host_mounts: list[dict[str, str]] | None,
        sandbox_secret: str,
    ) -> SandboxInstance:
        """Spin up a sandbox and return a handle to it."""
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
