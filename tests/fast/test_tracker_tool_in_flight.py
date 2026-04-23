"""Tests for SubagentTracker: in-flight tools skip stuck detection."""

import time

from agent_session.tracker import SubagentTracker
from tests.fast.conftest import _DEFAULT_RUN_CONFIG


class TestTrackerToolInFlight:
    """Subagents with tools in-flight must not be flagged as stuck."""

    def test_in_flight_skips_stuck(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("a1", "builder")
        tracker._started_at["a1"] = time.time() - 700
        tracker._last_tool_at["a1"] = time.time() - 700
        tracker.record_tool_use("a1")

        stuck = tracker.stuck_subagents()
        assert len(stuck) == 0

    def test_done_resumes_stuck_detection(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker.record_tool_done("a1")
        # Backdate after the cycle so the agent appears idle.
        tracker._started_at["a1"] = time.time() - 700
        tracker._last_tool_at["a1"] = time.time() - 700

        stuck = tracker.stuck_subagents()
        assert len(stuck) == 1
        assert stuck[0].agent_id == "a1"

    def test_has_tools_in_flight(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        assert not tracker.has_tools_in_flight()

        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        assert tracker.has_tools_in_flight()

        tracker.record_tool_done("a1")
        assert not tracker.has_tools_in_flight()
