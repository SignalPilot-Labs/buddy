"""Tests for StreamProcessor SSE event dispatch with asyncio.wait racing."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.event_bus import EventBus
from core.stream import StreamProcessor
from core.control import ControlHandler
from utils.models import ControlAction, RunContext


async def mock_stream(events):
    """Async generator that yields pre-built SSE events."""
    for event in events:
        yield event


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


def _make_control():
    """Build a mock ControlHandler."""
    control = MagicMock(spec=ControlHandler)
    control.handle_event = AsyncMock(return_value=ControlAction.no_action())
    control.on_subagent_complete = AsyncMock()
    control.handle_rate_limit = AsyncMock(return_value=ControlAction.no_action())
    return control


def _make_processor(sandbox, run_context, session, tracker, control, events):
    """Construct a StreamProcessor with the given mocks."""
    return StreamProcessor(
        sandbox=sandbox,
        session_id="sess-1",
        run_context=run_context,
        session=session,
        tracker=tracker,
        control=control,
        events=events,
    )


def _build_mocks():
    """Create the standard set of mocks for StreamProcessor dependencies."""
    sandbox = MagicMock()
    sandbox.interrupt_session = AsyncMock()
    sandbox.send_message = AsyncMock()
    session = MagicMock()
    session.has_ended.return_value = False
    session.elapsed_minutes.return_value = 1.0
    tracker = MagicMock()
    control = _make_control()
    events = EventBus()
    return sandbox, session, tracker, control, events


class TestStreamProcessor:
    """Tests for StreamProcessor.process() event handling."""

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_assistant_message_logs_and_accumulates_usage(self, mock_db):
        """assistant_message events accumulate token usage."""
        sandbox, session, tracker, control, events = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {
                "event": "assistant_message",
                "data": {
                    "content": [
                        {"type": "text", "text": "Hello world"},
                        {"type": "tool_use", "name": "Bash"},
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        result = await proc.process()

        assert run_context.total_input_tokens == 10
        assert run_context.total_output_tokens == 5
        assert not result.should_stop

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_rate_limit_rejected_returns_final_status(self, mock_db):
        """rate_limit with rejected status stops the loop."""
        sandbox, session, tracker, control, events = _build_mocks()
        control.handle_rate_limit = AsyncMock(
            return_value=ControlAction(
                stop=True, break_stream=False, final_status="rate_limited",
            ),
        )
        sandbox.stream_events.return_value = mock_stream([
            {
                "event": "rate_limit",
                "data": {"status": "rejected", "resets_at": None},
            },
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        result = await proc.process()

        assert result.should_stop is True
        assert result.final_status == "rate_limited"

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_result_event_saves_cost_and_usage(self, mock_db):
        """result event updates cost and token counts on context."""
        sandbox, session, tracker, control, events = _build_mocks()
        mock_db.save_session_id = AsyncMock()
        mock_db.log_audit = AsyncMock()
        sandbox.stream_events.return_value = mock_stream([
            {
                "event": "result",
                "data": {
                    "session_id": "sess-abc",
                    "total_cost_usd": 1.25,
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                    "num_turns": 3,
                },
            },
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        result = await proc.process()

        assert run_context.total_cost == 1.25
        assert run_context.total_input_tokens == 100
        assert run_context.total_output_tokens == 50
        mock_db.save_session_id.assert_awaited_once_with("run-1", "sess-abc")

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_session_end_breaks_loop(self, mock_db):
        """session_end lets the SSE stream close naturally, should_stop stays False."""
        sandbox, session, tracker, control, events = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "session_end", "data": {}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        result = await proc.process()

        assert not result.should_stop

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_session_error_breaks_loop_and_logs(self, mock_db, caplog):
        """session_error event breaks the loop and logs the error."""
        sandbox, session, tracker, control, events = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "session_error", "data": {"error": "boom"}},
            {"event": "assistant_message", "data": {"content": [{"type": "text", "text": "after"}]}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        with caplog.at_level(logging.ERROR, logger="core.stream"):
            result = await proc.process()

        assert "boom" in caplog.text

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_end_session_marks_session_ended(self, mock_db):
        """end_session event calls mark_ended on SessionGate."""
        sandbox, session, tracker, control, events = _build_mocks()
        session.has_ended.return_value = True
        sandbox.stream_events.return_value = mock_stream([
            {"event": "end_session", "data": {}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        result = await proc.process()

        session.mark_ended.assert_called_once()
        assert result.session_ended is True

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_end_session_denied_just_logs(self, mock_db, caplog):
        """end_session_denied logs a message but does not mark session ended."""
        sandbox, session, tracker, control, events = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "end_session_denied", "data": {}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        with caplog.at_level(logging.INFO, logger="core.stream"):
            result = await proc.process()

        session.mark_ended.assert_not_called()
        assert "end_session denied" in caplog.text
        assert not result.session_ended

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_subagent_start_calls_tracker(self, mock_db):
        """subagent_start event calls track_subagent_start on SubagentTracker."""
        sandbox, session, tracker, control, events = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "subagent_start", "data": {"agent_id": "a1", "agent_type": "builder"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        await proc.process()

        tracker.track_subagent_start.assert_called_once_with("a1", "builder")

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_subagent_stop_calls_tracker_and_control(self, mock_db):
        """subagent_stop event calls tracker and control.on_subagent_complete."""
        sandbox, session, tracker, control, events = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "subagent_stop", "data": {"agent_id": "a1"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        await proc.process()

        tracker.track_subagent_stop.assert_called_once_with("a1")
        control.on_subagent_complete.assert_awaited_once_with(run_context)

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_tool_use_calls_tracker(self, mock_db):
        """tool_use event calls track_tool_use on SubagentTracker."""
        sandbox, session, tracker, control, events = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "tool_use", "data": {"agent_id": "a1"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        await proc.process()

        tracker.track_tool_use.assert_called_once_with("a1")

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_control_stop_interrupts_immediately(self, mock_db):
        """Stop event via EventBus interrupts even when SSE is idle."""
        sandbox, session, tracker, control, events = _build_mocks()
        control.handle_event = AsyncMock(
            return_value=ControlAction(stop=True, break_stream=False, final_status="stopped"),
        )

        async def slow_stream():
            """Simulate an SSE stream that blocks for a long time."""
            import asyncio
            await asyncio.sleep(10)  # would block forever in old design
            yield {"event": "assistant_message", "data": {"content": []}}

        sandbox.stream_events.return_value = slow_stream()
        events.push("stop", "operator stop")

        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        result = await proc.process()

        assert result.should_stop is True
        assert result.final_status == "stopped"

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_control_break_stream_exits_loop(self, mock_db):
        """ControlHandler break_stream exits the event loop."""
        sandbox, session, tracker, control, events = _build_mocks()
        control.handle_event = AsyncMock(
            return_value=ControlAction(stop=False, break_stream=True, final_status=None),
        )

        async def slow_stream():
            import asyncio
            await asyncio.sleep(10)
            yield {"event": "assistant_message", "data": {"content": []}}

        sandbox.stream_events.return_value = slow_stream()
        events.push("pause", None)

        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        result = await proc.process()

        assert not result.should_stop
        assert not result.session_ended

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_subagent_start_without_agent_id_is_ignored(self, mock_db):
        """subagent_start with empty agent_id does not call tracker."""
        sandbox, session, tracker, control, events = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "subagent_start", "data": {"agent_id": "", "agent_type": "builder"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, control, events)
        await proc.process()

        tracker.track_subagent_start.assert_not_called()
