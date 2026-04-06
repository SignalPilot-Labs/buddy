"""Tests for StreamProcessor SSE event dispatch."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.stream import StreamProcessor
from utils.models import RunContext


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


def _make_processor(sandbox, run_context, session, tracker, events, prompts):
    """Construct a StreamProcessor with the given mocks."""
    return StreamProcessor(
        sandbox=sandbox,
        session_id="sess-1",
        run_context=run_context,
        session=session,
        tracker=tracker,
        events=events,
        prompts=prompts,
        model="opus",
        fallback_model=None,
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
    events = MagicMock()
    events.drain = AsyncMock(return_value=None)
    prompts = MagicMock()
    return sandbox, session, tracker, events, prompts


class TestStreamProcessor:
    """Tests for StreamProcessor.process() event handling."""

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_assistant_message_collects_text_and_tools(self, mock_db):
        """assistant_message events populate chunks and tools lists."""
        sandbox, session, tracker, events, prompts = _build_mocks()
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
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        result = await proc.process(0, False)

        assert result.round_text_chunks == ["Hello world"]
        assert result.round_tools == ["Bash"]
        assert run_context.total_input_tokens == 10
        assert run_context.total_output_tokens == 5
        assert not result.should_stop

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_rate_limit_rejected_returns_final_status(self, mock_db):
        """rate_limit with rejected status stops the loop."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        mock_db.log_audit = AsyncMock()
        mock_db.update_run_status = AsyncMock()
        mock_db.save_rate_limit_reset = AsyncMock()
        sandbox.stream_events.return_value = mock_stream([
            {
                "event": "rate_limit",
                "data": {"status": "rejected", "resets_at": None},
            },
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        result = await proc.process(0, False)

        assert result.should_stop is True
        assert result.final_status == "rate_limited"

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_result_event_saves_cost_and_usage(self, mock_db):
        """result event updates cost and token counts on context."""
        sandbox, session, tracker, events, prompts = _build_mocks()
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
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        result = await proc.process(0, False)

        assert run_context.total_cost == 1.25
        assert run_context.total_input_tokens == 100
        assert run_context.total_output_tokens == 50
        assert result.result_message is not None
        mock_db.save_session_id.assert_awaited_once_with("run-1", "sess-abc")

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_session_end_breaks_loop(self, mock_db):
        """session_end event breaks the processing loop."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "session_end", "data": {}},
            {"event": "assistant_message", "data": {"content": [{"type": "text", "text": "after"}]}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        result = await proc.process(0, False)

        assert result.round_text_chunks == []
        assert not result.should_stop

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_session_error_breaks_loop_and_logs(self, mock_db, caplog):
        """session_error event breaks the loop and logs the error."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "session_error", "data": {"error": "boom"}},
            {"event": "assistant_message", "data": {"content": [{"type": "text", "text": "after"}]}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        with caplog.at_level(logging.ERROR, logger="core.stream"):
            result = await proc.process(0, False)

        assert result.round_text_chunks == []
        assert "boom" in caplog.text

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_end_session_marks_session_ended(self, mock_db):
        """end_session event calls mark_ended on SessionGate."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        session.has_ended.return_value = True
        sandbox.stream_events.return_value = mock_stream([
            {"event": "end_session", "data": {}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        result = await proc.process(0, False)

        session.mark_ended.assert_called_once()
        assert result.session_ended is True

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_end_session_denied_just_logs(self, mock_db, caplog):
        """end_session_denied logs a message but does not mark session ended."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "end_session_denied", "data": {"reason": "time remaining"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        with caplog.at_level(logging.INFO, logger="core.stream"):
            result = await proc.process(0, False)

        session.mark_ended.assert_not_called()
        assert "time remaining" in caplog.text
        assert not result.session_ended

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_subagent_start_calls_tracker(self, mock_db):
        """subagent_start event calls track_subagent_start on SubagentTracker."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "subagent_start", "data": {"agent_id": "a1", "agent_type": "builder"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        await proc.process(0, False)

        tracker.track_subagent_start.assert_called_once_with("a1", "builder")

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_subagent_stop_calls_tracker(self, mock_db):
        """subagent_stop event calls track_subagent_stop on SubagentTracker."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "subagent_stop", "data": {"agent_id": "a1"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        await proc.process(0, False)

        tracker.track_subagent_stop.assert_called_once_with("a1")

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_tool_use_calls_tracker(self, mock_db):
        """tool_use event calls track_tool_use on SubagentTracker."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "tool_use", "data": {"agent_id": "a1"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        await proc.process(0, False)

        tracker.track_tool_use.assert_called_once_with("a1")

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_stop_event_from_bus_returns_stopped(self, mock_db):
        """EventBus stop event interrupts sandbox and returns stopped status."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        mock_db.log_audit = AsyncMock()
        sandbox.interrupt_session = AsyncMock()
        events.drain = AsyncMock(return_value={"event": "stop", "payload": "user stop"})
        sandbox.stream_events.return_value = mock_stream([
            {"event": "assistant_message", "data": {"content": []}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        result = await proc.process(0, False)

        assert result.should_stop is True
        assert result.final_status == "stopped"
        sandbox.interrupt_session.assert_awaited_once_with("sess-1")

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_rate_limit_ignored_during_planning(self, mock_db):
        """rate_limit events are skipped when is_planning=True."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "rate_limit", "data": {"status": "rejected"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        result = await proc.process(0, True)

        assert not result.should_stop
        assert result.final_status is None

    @pytest.mark.asyncio
    @patch("core.stream.db", new_callable=MagicMock)
    async def test_subagent_start_without_agent_id_is_ignored(self, mock_db):
        """subagent_start with empty agent_id does not call tracker."""
        sandbox, session, tracker, events, prompts = _build_mocks()
        sandbox.stream_events.return_value = mock_stream([
            {"event": "subagent_start", "data": {"agent_id": "", "agent_type": "builder"}},
        ])
        run_context = _make_ctx()
        proc = _make_processor(sandbox, run_context, session, tracker, events, prompts)
        await proc.process(0, False)

        tracker.track_subagent_start.assert_not_called()
