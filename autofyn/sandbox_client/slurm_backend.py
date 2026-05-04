"""Slurm sandbox backend — runs sandboxes on HPC clusters via connector.

Uses SSH + srun/sbatch through the connector. Inherits all lifecycle
logic from BaseRemoteBackend.
"""

import logging

from sandbox_client.base_remote import BaseRemoteBackend

log = logging.getLogger("sandbox_client.slurm_backend")


class SlurmBackend(BaseRemoteBackend):
    """Remote Slurm via connector."""

    def __init__(
        self,
        connector_url: str,
        connector_secret: str,
        sandbox_id: str,
        ssh_target: str,
        heartbeat_timeout: int,
    ) -> None:
        """Initialize with Slurm sandbox type."""
        super().__init__(
            connector_url=connector_url,
            connector_secret=connector_secret,
            sandbox_id=sandbox_id,
            ssh_target=ssh_target,
            sandbox_type="slurm",
            heartbeat_timeout=heartbeat_timeout,
        )
