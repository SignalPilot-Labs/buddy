"""Tests for SessionRunner asyncio.wait event loop racing."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.event_bus import EventBus
from core.session_runner import SessionRunner
from core.control import ControlHandler
from core.sse_dispatch import SSEDispatcher
from utils.models import ControlAction, RunContext


def _make_ctx():
    """Build a minimal RunContext for tests."""
    return RunContext(
        run_id="run-1",
        agent_role="builder",
        branch_name="feat/test",
        base_branch="main",
        duration_minutes=60.0,
        github_repo="owner/repo",
    )


class TestSessionRunnerProcessStream:
    """Tests for SessionRunner._process_stream() event loop racing."""

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_control_stop_interrupts_idle_sse(self, mock_db):
        """Stop event via EventBus interrupts even when SSE is idle."""
        sandbox = MagicMock()
        events = EventBus()
        session = MagicMock()
        session.has_ended.return_value = False
        tracker = MagicMock()

        control = MagicMock(spec=ControlHandler)
        control.handle_event = AsyncMock(
            return_value=ControlAction(stop=True, break_stream=False, final_status="stopped", pause=False),
        )

        dispatcher = SSEDispatcher(_make_ctx(), session, tracker)

        async def slow_stream():
            """SSE stream that blocks for a long time."""
            await asyncio.sleep(10)
            yield {"event": "assistant_message", "data": {"content": []}}

        sandbox.stream_events.return_value = slow_stream()
        events.push("stop", "operator stop")

        runner = SessionRunner(sandbox, MagicMock())
        result = await runner._process_stream(
            "sess-1", _make_ctx(), session, control, dispatcher, events,
        )

        assert result.should_stop is True
        assert result.final_status == "stopped"

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_control_break_stream_exits_loop(self, mock_db):
        """ControlHandler break_stream exits the event loop for re-entry."""
        sandbox = MagicMock()
        events = EventBus()
        session = MagicMock()
        session.has_ended.return_value = False
        tracker = MagicMock()

        control = MagicMock(spec=ControlHandler)
        control.handle_event = AsyncMock(
            return_value=ControlAction(stop=False, break_stream=True, final_status=None, pause=False),
        )

        dispatcher = SSEDispatcher(_make_ctx(), session, tracker)

        async def slow_stream():
            await asyncio.sleep(10)
            yield {"event": "assistant_message", "data": {"content": []}}

        sandbox.stream_events.return_value = slow_stream()
        events.push("pause", None)

        runner = SessionRunner(sandbox, MagicMock())
        result = await runner._process_stream(
            "sess-1", _make_ctx(), session, control, dispatcher, events,
        )

        assert not result.should_stop
        assert not result.session_ended

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_sse_stream_end_returns_cleanly(self, mock_db):
        """When SSE stream ends, process_stream returns without should_stop."""
        sandbox = MagicMock()
        events = EventBus()
        session = MagicMock()
        session.has_ended.return_value = False
        tracker = MagicMock()

        control = MagicMock(spec=ControlHandler)
        dispatcher = SSEDispatcher(_make_ctx(), session, tracker)

        async def empty_stream():
            return
            yield  # make it an async generator

        sandbox.stream_events.return_value = empty_stream()

        runner = SessionRunner(sandbox, MagicMock())
        result = await runner._process_stream(
            "sess-1", _make_ctx(), session, control, dispatcher, events,
        )

        assert not result.should_stop
