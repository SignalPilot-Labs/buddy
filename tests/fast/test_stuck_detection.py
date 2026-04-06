"""Tests for SubagentTracker.get_stuck_subagents() stuck detection."""

import time

from tools.subagent_tracker import SubagentTracker


class TestStuckSubagentDetection:
    """Tests for SubagentTracker.get_stuck_subagents()."""

    def test_stuck_includes_agent_type(self):
        tracker = SubagentTracker()
        agent_id = "test-agent-123"
        tracker.track_subagent_start(agent_id, "builder")
        tracker._subagent_start_times[agent_id] = time.time() - 700

        stuck = tracker.get_stuck_subagents()
        assert len(stuck) == 1
        assert stuck[0]["agent_id"] == agent_id
        assert stuck[0]["agent_type"] == "builder"
        assert stuck[0]["idle_seconds"] >= 700

    def test_not_stuck_if_recent_tool(self):
        tracker = SubagentTracker()
        agent_id = "test-agent-456"
        tracker.track_subagent_start(agent_id, "reviewer")
        tracker._subagent_start_times[agent_id] = time.time() - 700
        tracker.track_tool_use(agent_id)

        stuck = tracker.get_stuck_subagents()
        assert len(stuck) == 0

    def test_unknown_agent_type_fallback(self):
        tracker = SubagentTracker()
        agent_id = "test-agent-789"
        tracker._subagent_start_times[agent_id] = time.time() - 700

        stuck = tracker.get_stuck_subagents()
        assert len(stuck) == 1
        assert stuck[0]["agent_type"] == "unknown"
