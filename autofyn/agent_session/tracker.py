"""Subagent tracker — per-round timing, stuck detection, tool watchdog.

One SubagentTracker per round. Records when subagents start, when they
last used a tool, and flags ones that have been idle longer than
run_config.subagent_idle_kill_sec. Also tracks per-agent tool start times
so the pulse loop can detect tool calls exceeding
run_config.tool_call_timeout_sec.

The StuckSubagent dataclass lives in utils.models.
"""

import logging
import time

from utils.models import StuckSubagent
from utils.run_config import RunAgentConfig

log = logging.getLogger("session.tracker")

# Sentinel for orchestrator-level tool tracking (no agent_id).
ORCHESTRATOR_ID = "__orchestrator__"


class SubagentTracker:
    """In-memory timing tracker for subagents and tool calls in a round.

    Public API:
        record_start(agent_id, agent_type)
        record_stop(agent_id)
        record_tool_use(agent_id)
        record_tool_done(agent_id)
        active_count()
        has_tools_in_flight()
        stuck_subagents()
        timed_out_tools()
    """

    def __init__(self, run_config: RunAgentConfig) -> None:
        self._run_config = run_config
        self._started_at: dict[str, float] = {}
        self._last_tool_at: dict[str, float] = {}
        self._types: dict[str, str] = {}
        self._tools_in_flight: dict[str, int] = {}
        # Earliest in-flight tool start per agent (or ORCHESTRATOR_ID).
        self._tool_started_at: dict[str, float] = {}

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
        self._tools_in_flight.pop(agent_id, None)
        self._tool_started_at.pop(agent_id, None)

    def record_tool_use(self, agent_id: str | None) -> None:
        """Reset the idle timer and mark a tool in-flight.

        When agent_id is None the tool belongs to the orchestrator itself.
        """
        now = time.time()
        key = agent_id if agent_id and agent_id in self._started_at else ORCHESTRATOR_ID
        if key != ORCHESTRATOR_ID:
            self._last_tool_at[key] = now
        self._tools_in_flight[key] = self._tools_in_flight.get(key, 0) + 1
        if key not in self._tool_started_at:
            self._tool_started_at[key] = now

    def record_tool_done(self, agent_id: str | None) -> None:
        """Mark one tool finished.

        When agent_id is None the tool belongs to the orchestrator itself.
        """
        key = agent_id if agent_id and agent_id in self._started_at else ORCHESTRATOR_ID
        if key not in self._tools_in_flight:
            return
        self._tools_in_flight[key] = max(0, self._tools_in_flight[key] - 1)
        if self._tools_in_flight[key] == 0:
            self._tool_started_at.pop(key, None)

    def active_count(self) -> int:
        """Number of subagents currently tracked as active."""
        return len(self._started_at)

    def has_tools_in_flight(self) -> bool:
        """True if any tool call is currently executing."""
        return any(c > 0 for c in self._tools_in_flight.values())

    def stuck_subagents(self) -> list[StuckSubagent]:
        """Return subagents idle longer than subagent_idle_kill_sec.

        Subagents with tools still in-flight are never considered stuck.
        """
        now = time.time()
        result: list[StuckSubagent] = []
        for agent_id, started in self._started_at.items():
            if self._tools_in_flight.get(agent_id, 0) > 0:
                continue
            last = self._last_tool_at.get(agent_id, started)
            idle = now - last
            if idle > self._run_config.subagent_idle_kill_sec:
                result.append(StuckSubagent(
                    agent_id=agent_id,
                    agent_type=self._types[agent_id],
                    idle_seconds=int(idle),
                    total_seconds=int(now - started),
                ))
        return result

    def clear_tool_state(self, key: str) -> None:
        """Reset in-flight count and start time for `key` after a timeout."""
        self._tools_in_flight.pop(key, None)
        self._tool_started_at.pop(key, None)

    def timed_out_tools(self) -> list[tuple[str, int]]:
        """Return (agent_key, elapsed_sec) for tools exceeding tool_call_timeout_sec."""
        now = time.time()
        result: list[tuple[str, int]] = []
        for key, started in self._tool_started_at.items():
            elapsed = int(now - started)
            if elapsed > self._run_config.tool_call_timeout_sec:
                result.append((key, elapsed))
        return result
