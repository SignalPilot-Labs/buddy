"""Abstract base class for sandbox backends.

Defines the contract that all sandbox backends (local Docker, remote
Docker, remote Slurm) must implement. The pool calls these methods
without knowing the underlying infrastructure.
"""

from abc import ABC, abstractmethod

from sandbox_client.models import SandboxInstance


class SandboxBackend(ABC):
    """Base class for all sandbox backends."""

    @abstractmethod
    async def create(
        self,
        run_key: str,
        health_timeout: int,
        host_mounts: list[dict[str, str]] | None,
        sandbox_secret: str,
        start_cmd: str | None,
    ) -> tuple[SandboxInstance, list[dict]]:
        """Spin up a sandbox and return (handle, startup_events).

        Local backends ignore start_cmd and return empty events.
        Remote backends require start_cmd and return NDJSON events.
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
