"""Heartbeat tracker for abandoned sandbox self-termination.

Tracks the last HTTP request time. If no request arrives within the
heartbeat timeout, the sandbox exits gracefully. The connector sends
explicit heartbeat pings to keep the sandbox alive.
"""

import asyncio
import logging
import os
import time

from constants import (
    SANDBOX_HEARTBEAT_CHECK_INTERVAL_SEC,
    SANDBOX_HEARTBEAT_TIMEOUT_ENV_VAR,
)

log = logging.getLogger("sandbox.heartbeat")


class HeartbeatTracker:
    """Tracks last request time and self-terminates if abandoned."""

    def __init__(self) -> None:
        """Initialize the tracker with current time and configured timeout."""
        self._last_request: float = time.monotonic()
        timeout_str = os.environ.get(SANDBOX_HEARTBEAT_TIMEOUT_ENV_VAR, "")
        self._timeout: int = int(timeout_str) if timeout_str else 0
        self._task: asyncio.Task[None] | None = None

    def touch(self) -> None:
        """Record that an HTTP request was received."""
        self._last_request = time.monotonic()

    def start(self) -> None:
        """Start the background watchdog if a timeout is configured."""
        if self._timeout <= 0:
            log.info("Heartbeat self-termination disabled (no timeout configured)")
            return
        log.info("Heartbeat timeout: %ds", self._timeout)
        self._task = asyncio.create_task(self._watchdog())

    def stop(self) -> None:
        """Cancel the background watchdog."""
        if self._task:
            self._task.cancel()
            self._task = None

    async def _watchdog(self) -> None:
        """Periodically check if heartbeat has timed out."""
        while True:
            await asyncio.sleep(SANDBOX_HEARTBEAT_CHECK_INTERVAL_SEC)
            elapsed = time.monotonic() - self._last_request
            if elapsed > self._timeout:
                log.warning(
                    "No request for %.0fs (timeout=%ds) — self-terminating",
                    elapsed,
                    self._timeout,
                )
                os._exit(0)
