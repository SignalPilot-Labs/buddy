"""Subagent tracker — per-round timing and stuck detection.

One SubagentTracker per round. Records when subagents start, when they
last used a tool, and flags ones that have been idle longer than
SUBAGENT_IDLE_KILL_SEC. The StuckSubagent dataclass lives in utils.models.
"""

import logging
import time

from utils.constants import SUBAGENT_IDLE_KILL_SEC
from utils.models import StuckSubagent

log = logging.getLogger("session.tracker")


class SubagentTracker:
    """In-memory timing tracker for subagents active in a round.

    Public API:
        record_start(agent_id, agent_type)
        record_stop(agent_id)
        record_tool_use(agent_id)
        stuck_subagents()
        active_count()
    """

    def __init__(self) -> None:
        self._started_at: dict[str, float] = {}
        self._last_tool_at: dict[str, float] = {}
        self._types: dict[str, str] = {}

    def record_start(self, agent_id: str, agent_type: str) -> None:
        """Remember that `agent_id` of type `agent_type` has started."""
        now = time.time()
        self._started_at[agent_id] = now
        self._last_tool_at[agent_id] = now
        self._types[agent_id] = agent_type

    def record_stop(self, agent_id: str) -> None:
        """Forget a subagent that has finished cleanly."""
        self._started_at.pop(agent_id, None)
        self._last_tool_at.pop(agent_id, None)
        self._types.pop(agent_id, None)

    def record_tool_use(self, agent_id: str) -> None:
        """Reset the idle timer for `agent_id`."""
        if agent_id in self._started_at:
            self._last_tool_at[agent_id] = time.time()

    def active_count(self) -> int:
        """Number of subagents currently tracked as active."""
        return len(self._started_at)

    def stuck_subagents(self) -> list[StuckSubagent]:
        """Return subagents idle longer than SUBAGENT_IDLE_KILL_SEC."""
        now = time.time()
        result: list[StuckSubagent] = []
        for agent_id, started in self._started_at.items():
            last = self._last_tool_at.get(agent_id, started)
            idle = now - last
            if idle > SUBAGENT_IDLE_KILL_SEC:
                result.append(StuckSubagent(
                    agent_id=agent_id,
                    agent_type=self._types.get(agent_id, "unknown"),
                    idle_seconds=int(idle),
                    total_seconds=int(now - started),
                ))
        return result
