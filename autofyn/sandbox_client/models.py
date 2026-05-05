"""Data models and exceptions for the sandbox_client package."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxInstance:
    """Opaque reference to a running sandbox.

    Returned by SandboxBackend.create() and passed to destroy(). The agent
    uses `url` for all HTTP communication and never needs to know whether
    the sandbox is local or remote.
    """

    run_key: str
    url: str
    sandbox_secret: str
    sandbox_id: str | None


class SandboxStartError(Exception):
    """Raised when the sandbox fails to start."""

    def __init__(self, message: str, startup_logs: list[dict]) -> None:
        """Initialize with message and the NDJSON startup logs for debugging."""
        self.startup_logs = startup_logs
        super().__init__(message)
