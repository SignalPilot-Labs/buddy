"""TimeLock — per-run time budget tracker.

Replaces the old `tools.session.SessionGate`. Pure in-process timing
state; the sandbox-side session manager owns the actual `end_session`
MCP tool and its early-exit logic. This class exists so the health
endpoint and round loop can see how much time is left and whether the
run has been force-unlocked by the user.
"""

import time


class TimeLock:
    """Run-scoped time budget and force-unlock flag.

    Public API:
        elapsed_minutes()
        remaining_minutes()
        time_remaining_str()
        is_expired()
        is_force_unlocked()
        force_unlock()
    """

    def __init__(self, duration_minutes: float) -> None:
        self._start = time.time()
        self._duration_sec = duration_minutes * 60
        self._force_unlocked = False

    def force_unlock(self) -> None:
        """Mark the time lock as manually unlocked by the user."""
        self._force_unlocked = True

    def is_force_unlocked(self) -> bool:
        """True if the user force-unlocked this session."""
        return self._force_unlocked

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
        """Human-readable remaining time. Empty string if no duration set."""
        if self._duration_sec <= 0:
            return ""
        remaining = (self._start + self._duration_sec) - time.time()
        if remaining <= 0:
            return "0m"
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
