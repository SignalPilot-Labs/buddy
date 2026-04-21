"""Tests for SubagentTracker.stuck_subagents() detection."""

import time

import pytest

from agent_session.tracker import SubagentTracker
from utils.run_config import RunAgentConfig

_DEFAULT_RUN_CONFIG = RunAgentConfig(
    max_rounds=128,
    tool_call_timeout_sec=3600,
    session_idle_timeout_sec=120,
    subagent_idle_kill_sec=600,
)


class TestStuckSubagentDetection:
    """Tests for SubagentTracker.stuck_subagents()."""

    def test_stuck_includes_agent_type(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
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
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        agent_id = "test-agent-456"
        tracker.record_start(agent_id, "reviewer")
        tracker._started_at[agent_id] = time.time() - 700
        tracker.record_tool_use(agent_id)

        stuck = tracker.stuck_subagents()
        assert len(stuck) == 0

    def test_missing_agent_type_raises_key_error(self) -> None:
        """Accessing _types for an unregistered agent_id raises KeyError (fail-fast)."""
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        agent_id = "test-agent-789"
        # Register without a type by bypassing record_start.
        tracker._started_at[agent_id] = time.time() - 700
        tracker._last_tool_at[agent_id] = time.time() - 700

        with pytest.raises(KeyError):
            tracker.stuck_subagents()
