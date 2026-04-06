"""Session gate: time-lock logic for agent run duration.

SessionGate is a pure timing tracker. The sandbox handles the actual
end_session MCP tool and DB logging. This module only tracks elapsed time
and the force-unlock state for the agent loop.
"""

import time

from utils.models import RunContext


class SessionGate:
    """Time-locked session control for a single run.

    Public API:
        is_unlocked, force_unlock, elapsed_minutes, time_remaining_str,
        has_ended, mark_ended
    """

    def __init__(self, run_context: RunContext):
        self._start = time.time()
        self._duration_sec = run_context.duration_minutes * 60
        self._force_unlocked = False
        self._ended = False

    def force_unlock(self) -> None:
        """Called when operator sends an early unlock signal."""
        self._force_unlocked = True

    def is_unlocked(self) -> bool:
        """Check if end_session is currently allowed."""
        if self._force_unlocked:
            return True
        if self._duration_sec <= 0:
            return True
        return time.time() >= self._start + self._duration_sec

    def time_remaining_str(self) -> str:
        """Human-readable time remaining."""
        remaining = (self._start + self._duration_sec) - time.time()
        if remaining <= 0:
            return "0m"
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def elapsed_minutes(self) -> float:
        """Minutes elapsed since run start."""
        return (time.time() - self._start) / 60

    def mark_ended(self) -> None:
        """Mark session as ended (called when end_session SSE event arrives)."""
        self._ended = True

    def has_ended(self) -> bool:
        """Check if the session has been ended via the end_session tool."""
        return self._ended
