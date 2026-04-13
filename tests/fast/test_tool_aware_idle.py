"""Tests for tool-aware idle detection and tool timeout watchdog.

Covers:
- SubagentTracker: in-flight tools skip stuck detection, timed_out_tools(),
  orchestrator-level tracking, clear_tool_state.
- StreamDispatcher: tool_done handling, has_tools_in_flight, has_active_subagents.
"""

import time

import pytest

from session.stream import StreamDispatcher
from session.tracker import SubagentTracker, ORCHESTRATOR_ID
from utils.models import RunContext


def _make_run() -> RunContext:
    """Create a minimal RunContext for the dispatcher."""
    return RunContext(
        run_id="abcd1234-0000-0000-0000-000000000000",
        agent_role="worker",
        github_repo="org/repo",
        branch_name="fix/test",
        base_branch="main",
        duration_minutes=60,
        total_cost=0,
        total_input_tokens=0,
        total_output_tokens=0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _make_dispatcher() -> tuple[StreamDispatcher, SubagentTracker]:
    """Create a dispatcher and its tracker for testing."""
    tracker = SubagentTracker()
    dispatcher = StreamDispatcher(run=_make_run(), round_number=1, tracker=tracker)
    return dispatcher, tracker


class TestTrackerToolInFlight:
    """Subagents with tools in-flight must not be flagged as stuck."""

    def test_in_flight_skips_stuck(self) -> None:
        tracker = SubagentTracker()
        tracker.record_start("a1", "builder")
        tracker._started_at["a1"] = time.time() - 700
        tracker._last_tool_at["a1"] = time.time() - 700
        tracker.record_tool_use("a1")

        stuck = tracker.stuck_subagents()
        assert len(stuck) == 0

    def test_done_resumes_stuck_detection(self) -> None:
        tracker = SubagentTracker()
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
        tracker = SubagentTracker()
        assert not tracker.has_tools_in_flight()

        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        assert tracker.has_tools_in_flight()

        tracker.record_tool_done("a1")
        assert not tracker.has_tools_in_flight()


class TestTrackerOrchestratorTools:
    """Tool tracking for orchestrator-level calls (agent_id=None)."""

    def test_none_agent_routes_to_orchestrator(self) -> None:
        tracker = SubagentTracker()
        tracker.record_tool_use(None)

        assert tracker.has_tools_in_flight()
        assert ORCHESTRATOR_ID in tracker._tools_in_flight

    def test_orchestrator_tool_done(self) -> None:
        tracker = SubagentTracker()
        tracker.record_tool_use(None)
        tracker.record_tool_done(None)

        assert not tracker.has_tools_in_flight()

    def test_orchestrator_tool_timeout(self) -> None:
        tracker = SubagentTracker()
        tracker.record_tool_use(None)
        tracker._tool_started_at[ORCHESTRATOR_ID] = time.time() - 3700

        timed_out = tracker.timed_out_tools()
        assert len(timed_out) == 1
        assert timed_out[0][0] == ORCHESTRATOR_ID


class TestTrackerTimedOutTools:
    """TOOL_CALL_TIMEOUT_SEC watchdog detection."""

    def test_no_timeout_when_fresh(self) -> None:
        tracker = SubagentTracker()
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")

        assert len(tracker.timed_out_tools()) == 0

    def test_timeout_after_threshold(self) -> None:
        tracker = SubagentTracker()
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker._tool_started_at["a1"] = time.time() - 3700

        timed_out = tracker.timed_out_tools()
        assert len(timed_out) == 1
        assert timed_out[0][0] == "a1"
        assert timed_out[0][1] >= 3600

    def test_clear_tool_state(self) -> None:
        tracker = SubagentTracker()
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker._tool_started_at["a1"] = time.time() - 3700

        tracker.clear_tool_state("a1")
        assert not tracker.has_tools_in_flight()
        assert len(tracker.timed_out_tools()) == 0


class TestTrackerClearAfterTimeout:
    """clear_tool_state must fully reset so timed_out_tools doesn't re-flag."""

    def test_clear_prevents_re_detection(self) -> None:
        tracker = SubagentTracker()
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker._tool_started_at["a1"] = time.time() - 3700

        assert len(tracker.timed_out_tools()) == 1
        tracker.clear_tool_state("a1")
        assert len(tracker.timed_out_tools()) == 0
        # Subagent itself is still tracked (not stopped).
        assert tracker.active_count() == 1

    def test_clear_orchestrator_state(self) -> None:
        tracker = SubagentTracker()
        tracker.record_tool_use(None)
        tracker._tool_started_at[ORCHESTRATOR_ID] = time.time() - 3700

        tracker.clear_tool_state(ORCHESTRATOR_ID)
        assert not tracker.has_tools_in_flight()
        assert len(tracker.timed_out_tools()) == 0


class TestTrackerMultipleToolsInFlight:
    """Multiple concurrent tools per agent must all resolve."""

    def test_two_tools_one_done_still_in_flight(self) -> None:
        tracker = SubagentTracker()
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker.record_tool_use("a1")

        assert tracker._tools_in_flight["a1"] == 2
        tracker.record_tool_done("a1")
        assert tracker.has_tools_in_flight()
        tracker.record_tool_done("a1")
        assert not tracker.has_tools_in_flight()

    def test_tool_started_at_cleared_only_when_all_done(self) -> None:
        tracker = SubagentTracker()
        tracker.record_start("a1", "builder")
        tracker.record_tool_use("a1")
        tracker.record_tool_use("a1")

        tracker.record_tool_done("a1")
        assert "a1" in tracker._tool_started_at
        tracker.record_tool_done("a1")
        assert "a1" not in tracker._tool_started_at


class TestDispatcherToolDone:
    """StreamDispatcher must track tool_done events."""

    @pytest.mark.asyncio
    async def test_tool_done_decrements_in_flight(self) -> None:
        dispatcher, tracker = _make_dispatcher()

        await dispatcher.dispatch({"event": "tool_use", "data": {"agent_id": "a1"}})
        assert dispatcher.has_tools_in_flight()

        await dispatcher.dispatch({"event": "tool_done", "data": {"agent_id": "a1"}})
        assert not dispatcher.has_tools_in_flight()

    @pytest.mark.asyncio
    async def test_has_active_subagents(self) -> None:
        dispatcher, tracker = _make_dispatcher()
        assert not dispatcher.has_active_subagents()

        await dispatcher.dispatch(
            {"event": "subagent_start", "data": {"agent_id": "a1", "agent_type": "builder"}},
        )
        assert dispatcher.has_active_subagents()

        await dispatcher.dispatch(
            {"event": "subagent_stop", "data": {"agent_id": "a1"}},
        )
        assert not dispatcher.has_active_subagents()

    @pytest.mark.asyncio
    async def test_tool_done_without_use_floors_at_zero(self) -> None:
        dispatcher, _ = _make_dispatcher()

        await dispatcher.dispatch({"event": "tool_done", "data": {"agent_id": "a1"}})
        assert not dispatcher.has_tools_in_flight()
