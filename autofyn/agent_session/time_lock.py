"""TimeLock — per-run time budget tracker.

Replaces the old `tools.session.SessionGate`. Pure in-process timing
state; the sandbox-side session manager owns the actual `end_session`
MCP tool and its early-exit logic. This class exists so the health
endpoint and round loop can see how much time is left and whether the
run is locked.
"""

import time


class TimeLock:
    """Run-scoped time budget and lock state.

    Public API:
        locked              (property)
        unlock()
        elapsed_minutes()
        remaining_minutes()
        time_remaining_str()
        is_expired()
    """

    def __init__(self, duration_minutes: float) -> None:
        self._start = time.time()
        self._duration_sec = duration_minutes * 60
        self._locked = duration_minutes > 0
        self.grace_round_used: bool = False

    @property
    def locked(self) -> bool:
        """True if the session time gate is active."""
        return self._locked

    def unlock(self) -> None:
        """Remove the time lock."""
        self._locked = False

    def elapsed_minutes(self) -> float:
        """Minutes since the run started."""
        return (time.time() - self._start) / 60

    def remaining_minutes(self) -> float:
        """Minutes left on the time budget. Negative when expired."""
        if self._duration_sec <= 0:
            return 0.0
        remaining_sec = (self._start + self._duration_sec) - time.time()
        return remaining_sec / 60

    def is_expired(self) -> bool:
        """True if the duration has elapsed."""
        if self._duration_sec <= 0:
            return False
        return time.time() >= self._start + self._duration_sec

    def time_remaining_str(self) -> str:
        """Human-readable remaining time. Empty string if not locked."""
        if not self._locked:
            return ""
        remaining = (self._start + self._duration_sec) - time.time()
        if remaining <= 0:
            return "0m"
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
