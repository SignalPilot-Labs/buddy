"""Immutable handle representing a running sandbox instance.

Returned by SandboxBackend.create() and passed to destroy(). The agent
uses `url` for all HTTP communication and never needs to know whether
the sandbox is local or remote.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxHandle:
    """Opaque reference to a running sandbox."""

    run_key: str
    url: str
    backend_id: str | None
    sandbox_secret: str
    sandbox_id: str | None
    sandbox_type: str | None
    remote_host: str | None
    remote_port: int | None
