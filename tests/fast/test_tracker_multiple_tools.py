"""Tests for SubagentTracker: multiple concurrent tools per agent must all resolve."""

from agent_session.tracker import SubagentTracker
from tests.fast.conftest import _DEFAULT_RUN_CONFIG


class TestTrackerMultipleToolsInFlight:
    """Multiple concurrent tools per agent must all resolve."""

    def test_two_tools_one_done_still_in_flight(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker.record_tool_use("a1")

        assert tracker._tools_in_flight["a1"] == 2
        tracker.record_tool_done("a1")
        assert tracker.has_tools_in_flight()
        tracker.record_tool_done("a1")
        assert not tracker.has_tools_in_flight()

    def test_tool_started_at_cleared_only_when_all_done(self) -> None:
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker.record_tool_use("a1")

        tracker.record_tool_done("a1")
        assert "a1" in tracker._tool_started_at
        tracker.record_tool_done("a1")
        assert "a1" not in tracker._tool_started_at
