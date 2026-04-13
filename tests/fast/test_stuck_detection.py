"""Tests for SubagentTracker.stuck_subagents() detection."""

import time

from agent_session.tracker import SubagentTracker


class TestStuckSubagentDetection:
    """Tests for SubagentTracker.stuck_subagents()."""

    def test_stuck_includes_agent_type(self) -> None:
        tracker = SubagentTracker()
        agent_id = "test-agent-123"
        tracker.record_start(agent_id, "builder")
        # Backdate the start and last-tool time to simulate idleness.
        tracker._started_at[agent_id] = time.time() - 700
        tracker._last_tool_at[agent_id] = time.time() - 700

        stuck = tracker.stuck_subagents()
        assert len(stuck) == 1
        assert stuck[0].agent_id == agent_id
        assert stuck[0].agent_type == "builder"
        assert stuck[0].idle_seconds >= 700

    def test_not_stuck_if_recent_tool(self) -> None:
        tracker = SubagentTracker()
        agent_id = "test-agent-456"
        tracker.record_start(agent_id, "reviewer")
        tracker._started_at[agent_id] = time.time() - 700
        tracker.record_tool_use(agent_id)

        stuck = tracker.stuck_subagents()
        assert len(stuck) == 0

    def test_unknown_agent_type_fallback(self) -> None:
        tracker = SubagentTracker()
        agent_id = "test-agent-789"
        # Register without a type by bypassing record_start.
        tracker._started_at[agent_id] = time.time() - 700
        tracker._last_tool_at[agent_id] = time.time() - 700

        stuck = tracker.stuck_subagents()
        assert len(stuck) == 1
        assert stuck[0].agent_type == "unknown"
