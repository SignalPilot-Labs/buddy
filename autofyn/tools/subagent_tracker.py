"""Subagent timing tracker for stuck detection.

DB logging of tool calls happens directly in the sandbox.
This module only tracks in-memory timing for the pulse checker.
"""

import logging
import time

from utils.constants import SUBAGENT_IDLE_KILL_SEC

log = logging.getLogger("tools.subagent_tracker")


class SubagentTracker:
    """Tracks subagent timing for stuck detection.

    Public API:
        track_subagent_start(agent_id, agent_type) -> None
        track_subagent_stop(agent_id) -> None
        track_tool_use(agent_id) -> None
        get_stuck_subagents() -> list[dict]
    """

    def __init__(self) -> None:
        self._subagent_start_times: dict[str, float] = {}
        self._subagent_last_tool: dict[str, float] = {}
        self._subagent_types: dict[str, str] = {}

    def track_subagent_start(self, agent_id: str, agent_type: str) -> None:
        """Record a subagent starting."""
        self._subagent_start_times[agent_id] = time.time()
        self._subagent_types[agent_id] = agent_type

    def track_subagent_stop(self, agent_id: str) -> None:
        """Remove a subagent from tracking."""
        self._subagent_start_times.pop(agent_id, None)
        self._subagent_last_tool.pop(agent_id, None)
        self._subagent_types.pop(agent_id, None)

    def track_tool_use(self, agent_id: str) -> None:
        """Record that a subagent used a tool (resets idle timer)."""
        self._subagent_last_tool[agent_id] = time.time()

    def get_stuck_subagents(self) -> list[dict]:
        """Return subagents idle longer than the kill threshold."""
        now = time.time()
        return [
            {
                "agent_id": aid,
                "agent_type": self._subagent_types.get(aid, "unknown"),
                "idle_seconds": int(now - self._subagent_last_tool.get(aid, start_t)),
                "total_seconds": int(now - start_t),
            }
            for aid, start_t in self._subagent_start_times.items()
            if (now - self._subagent_last_tool.get(aid, start_t)) > SUBAGENT_IDLE_KILL_SEC
        ]
