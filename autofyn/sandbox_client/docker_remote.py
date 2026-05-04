"""Remote Docker sandbox backend — runs sandboxes on remote machines via connector.

Uses SSH + docker run through the connector. Inherits all lifecycle
logic from BaseRemoteBackend.
"""

import logging

from sandbox_client.base_remote import BaseRemoteBackend

log = logging.getLogger("sandbox_client.docker_remote")


class DockerRemoteBackend(BaseRemoteBackend):
    """Remote Docker via connector."""

    def __init__(
        self,
        connector_url: str,
        connector_secret: str,
        sandbox_id: str,
        ssh_target: str,
        heartbeat_timeout: int,
    ) -> None:
        """Initialize with Docker sandbox type."""
        super().__init__(
            connector_url=connector_url,
            connector_secret=connector_secret,
            sandbox_id=sandbox_id,
            ssh_target=ssh_target,
            sandbox_type="docker",
            heartbeat_timeout=heartbeat_timeout,
        )
