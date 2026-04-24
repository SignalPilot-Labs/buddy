"""Tests for SubagentTracker: clear_tool_state must fully reset so timed_out_tools doesn't re-flag."""

import time

from agent_session.tracker import ORCHESTRATOR_ID, SubagentTracker
from tests.fast.conftest import _DEFAULT_RUN_CONFIG


class TestTrackerClearAfterTimeout:
    """clear_tool_state must fully reset so timed_out_tools doesn't re-flag."""

    def test_clear_prevents_re_detection(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker._tool_started_at["a1"] = time.time() - 3700

        assert len(tracker.timed_out_tools()) == 1
        tracker.clear_tool_state("a1")
        assert len(tracker.timed_out_tools()) == 0
        # Subagent itself is still tracked (not stopped).
        assert tracker.active_count() == 1

    def test_clear_orchestrator_state(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_tool_use(None)
        tracker._tool_started_at[ORCHESTRATOR_ID] = time.time() - 3700

        tracker.clear_tool_state(ORCHESTRATOR_ID)
        assert not tracker.has_tools_in_flight()
        assert len(tracker.timed_out_tools()) == 0
