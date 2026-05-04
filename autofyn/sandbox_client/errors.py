"""Custom exceptions for the sandbox_client package."""


class SandboxStartError(Exception):
    """Raised when the sandbox fails to start (startup script exits with error or AF_READY never emitted)."""

    def __init__(self, message: str, startup_logs: list[dict]) -> None:
        self.startup_logs = startup_logs
        super().__init__(message)
