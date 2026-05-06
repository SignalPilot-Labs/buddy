"""Per-run forward state tracking for the connector."""

import asyncio
import collections
from dataclasses import dataclass, field

from cli.connector.constants import RING_BUFFER_MAX_LINES


@dataclass
class ForwardState:
    """Tracks an active remote sandbox tunnel."""

    run_key: str
    ssh_target: str
    sandbox_type: str
    local_port: int
    tunnel_process: asyncio.subprocess.Process
    start_process: asyncio.subprocess.Process | None
    sandbox_secret: str
    backend_id: str | None
    work_dir: str
    log_buffer: collections.deque[str] = field(
        default_factory=lambda: collections.deque(maxlen=RING_BUFFER_MAX_LINES)
    )
