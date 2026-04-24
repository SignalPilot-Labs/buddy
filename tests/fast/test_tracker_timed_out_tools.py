"""Tests for SubagentTracker: TOOL_CALL_TIMEOUT_SEC watchdog detection."""

import time

from agent_session.tracker import SubagentTracker
from tests.fast.conftest import _DEFAULT_RUN_CONFIG


class TestTrackerTimedOutTools:
    """TOOL_CALL_TIMEOUT_SEC watchdog detection."""

    def test_no_timeout_when_fresh(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")

        assert len(tracker.timed_out_tools()) == 0

    def test_timeout_after_threshold(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker._tool_started_at["a1"] = time.time() - 3700

        timed_out = tracker.timed_out_tools()
        assert len(timed_out) == 1
        assert timed_out[0][0] == "a1"
        assert timed_out[0][1] >= 3600

    def test_clear_tool_state(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker._tool_started_at["a1"] = time.time() - 3700

        tracker.clear_tool_state("a1")
        assert not tracker.has_tools_in_flight()
        assert len(tracker.timed_out_tools()) == 0
