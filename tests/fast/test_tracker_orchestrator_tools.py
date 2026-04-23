"""Tests for SubagentTracker: tool tracking for orchestrator-level calls."""

import time

from agent_session.tracker import ORCHESTRATOR_ID, SubagentTracker
from tests.fast.conftest import _DEFAULT_RUN_CONFIG


class TestTrackerOrchestratorTools:
    """Tool tracking for orchestrator-level calls (agent_id=None)."""

    def test_none_agent_routes_to_orchestrator(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_tool_use(None)

        assert tracker.has_tools_in_flight()
        assert ORCHESTRATOR_ID in tracker._tools_in_flight

    def test_orchestrator_tool_done(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_tool_use(None)
        tracker.record_tool_done(None)

        assert not tracker.has_tools_in_flight()

    def test_orchestrator_tool_timeout(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_tool_use(None)
        tracker._tool_started_at[ORCHESTRATOR_ID] = time.time() - 3700

        timed_out = tracker.timed_out_tools()
        assert len(timed_out) == 1
        assert timed_out[0][0] == ORCHESTRATOR_ID
