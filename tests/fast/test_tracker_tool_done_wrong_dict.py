"""Regression test: record_tool_done must check _started_at, not _tools_in_flight.

Before the fix, record_tool_done resolved the agent key by checking
agent_id in self._tools_in_flight. A registered subagent with no tool
in flight would fail the check and fall through to ORCHESTRATOR_ID,
decrementing the orchestrator's counter instead of early-returning.
"""

from agent_session.tracker import ORCHESTRATOR_ID, SubagentTracker
from tests.fast.conftest import _DEFAULT_RUN_CONFIG


class TestTrackerToolDoneWrongDict:
    """Spurious record_tool_done for a subagent must not affect orchestrator counter."""

    def test_spurious_tool_done_does_not_decrement_orchestrator(self) -> None:
        """Subagent with no tools in flight: tool_done must not touch orchestrator count."""
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)

        # Register the subagent (puts it in _started_at, not _tools_in_flight)
        tracker.record_start("agent-1", "builder")

        # Give the orchestrator one tool in flight
        tracker.record_tool_use(None)
        assert tracker._tools_in_flight.get(ORCHESTRATOR_ID, 0) == 1

        # Spurious tool_done for the subagent (it has no tool in flight)
        tracker.record_tool_done("agent-1")

        # Orchestrator counter must remain at 1 — no decrement
        assert tracker._tools_in_flight.get(ORCHESTRATOR_ID, 0) == 1
        assert tracker.has_tools_in_flight()

    def test_normal_tool_done_for_registered_agent(self) -> None:
        """record_tool_done works correctly when the subagent has a tool in flight."""
        tracker = SubagentTracker(_DEFAULT_RUN_CONFIG)
        tracker.record_start("agent-2", "reviewer")
        tracker.record_tool_use("agent-2")

        assert tracker._tools_in_flight.get("agent-2", 0) == 1
        tracker.record_tool_done("agent-2")
        assert tracker._tools_in_flight.get("agent-2", 0) == 0
