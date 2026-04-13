"""Tests for session_error signal propagation through stream and runner layers.

Verifies that:
1. StreamDispatcher emits 'session_error' (not 'round_complete') for session_error events
2. StreamDispatcher still emits 'round_complete' for normal session_end events
3. RoundRunner._apply_signal maps 'session_error' to RoundResult(status='session_error')
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from session.stream import StreamDispatcher
from session.tracker import SubagentTracker
from utils.models import RunContext, StreamSignal


def _make_run() -> RunContext:
    """Create a minimal RunContext for the dispatcher."""
    run = RunContext(
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
    return run


def _make_dispatcher() -> StreamDispatcher:
    """Create a StreamDispatcher for testing."""
    return StreamDispatcher(
        run=_make_run(),
        round_number=1,
        tracker=SubagentTracker(),
    )


class TestStreamDispatcherSessionError:
    """StreamDispatcher must distinguish session_error from session_end."""

    @pytest.mark.asyncio
    async def test_session_error_returns_session_error_signal(self):
        """session_error event must produce StreamSignal(kind='session_error')."""
        dispatcher = _make_dispatcher()
        event = {"event": "session_error", "data": {"error": "500 Internal Server Error"}}

        signal = await dispatcher.dispatch(event)

        assert signal.kind == "session_error"
        assert signal.error == "500 Internal Server Error"

    @pytest.mark.asyncio
    async def test_session_end_returns_round_complete_signal(self):
        """Normal session_end must still produce round_complete."""
        dispatcher = _make_dispatcher()
        event = {"event": "session_end", "data": {}}

        signal = await dispatcher.dispatch(event)

        assert signal.kind == "round_complete"

    @pytest.mark.asyncio
    async def test_session_error_unknown_error_defaults(self):
        """Missing error field defaults to 'unknown'."""
        dispatcher = _make_dispatcher()
        event = {"event": "session_error", "data": {}}

        signal = await dispatcher.dispatch(event)

        assert signal.kind == "session_error"
        assert signal.error == "unknown"


class TestApplySignalSessionError:
    """RoundRunner._apply_signal must map session_error to RoundResult."""

    @pytest.mark.asyncio
    async def test_session_error_signal_produces_session_error_result(self):
        """session_error StreamSignal → RoundResult(status='session_error')."""
        from session.runner import RoundRunner

        runner = RoundRunner(
            sandbox=MagicMock(),
            run=_make_run(),
            inbox=MagicMock(),
            time_lock=MagicMock(),
        )
        signal = StreamSignal(kind="session_error", error="401 Unauthorized")
        control = MagicMock()

        result = await runner._apply_signal(signal, "sess-1", control, 1)

        assert result is not None
        assert result.status == "session_error"
        assert result.session_id == "sess-1"
        assert result.error == "401 Unauthorized"

    @pytest.mark.asyncio
    async def test_round_complete_signal_still_works(self):
        """round_complete StreamSignal → RoundResult(status='complete')."""
        from session.runner import RoundRunner

        runner = RoundRunner(
            sandbox=MagicMock(),
            run=_make_run(),
            inbox=MagicMock(),
            time_lock=MagicMock(),
        )
        signal = StreamSignal(kind="round_complete", round_summary="done")
        control = MagicMock()

        result = await runner._apply_signal(signal, "sess-1", control, 1)

        assert result is not None
        assert result.status == "complete"
        assert result.round_summary == "done"
