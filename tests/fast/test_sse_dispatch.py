"""Tests for SSEDispatcher event routing."""

import logging
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from core.sse_dispatch import SSEDispatcher
from utils.models import RunContext


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


def _make_dispatcher(run_context, session, tracker):
    """Construct an SSEDispatcher with the given mocks."""
    return SSEDispatcher(
        run_context=run_context,
        session=session,
        tracker=tracker,
    )


def _build_mocks():
    """Create the standard set of mocks for SSEDispatcher dependencies."""
    session = MagicMock()
    session.has_ended.return_value = False
    session.elapsed_minutes.return_value = 1.0
    tracker = MagicMock()
    return session, tracker


class TestSSEDispatcher:
    """Tests for SSEDispatcher.dispatch() event handling."""

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_assistant_message_accumulates_usage(self, mock_db):
        """assistant_message events accumulate token usage including cache tokens."""
        mock_db.log_audit = AsyncMock()
        session, tracker = _build_mocks()
        run_context = _make_ctx()
        dispatcher = _make_dispatcher(run_context, session, tracker)
        dispatched = await dispatcher.dispatch({
            "event": "assistant_message",
            "data": {
                "content": [
                    {"type": "text", "text": "Hello world"},
                    {"type": "tool_use", "name": "Bash"},
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_creation_input_tokens": 3,
                    "cache_read_input_tokens": 2,
                },
            },
        })

        assert run_context.total_input_tokens == 10
        assert run_context.total_output_tokens == 5
        assert run_context.cache_creation_input_tokens == 3
        assert run_context.cache_read_input_tokens == 2
        assert dispatched.result_data is None
        assert not dispatched.subagent_completed

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_rate_limit_returns_data(self, mock_db):
        """rate_limit event returns rate_limit_data for session runner to handle."""
        session, tracker = _build_mocks()
        dispatcher = _make_dispatcher(_make_ctx(), session, tracker)
        dispatched = await dispatcher.dispatch({
            "event": "rate_limit",
            "data": {"status": "rejected", "resets_at": None},
        })

        assert dispatched.rate_limit_data == {"status": "rejected", "resets_at": None}
        assert dispatched.result_data is None

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_result_event_saves_cost(self, mock_db):
        """result event adds cost and persists to DB."""
        mock_db.save_session_id = AsyncMock()
        mock_db.log_audit = AsyncMock()
        mock_db.update_run_cost = AsyncMock()
        session, tracker = _build_mocks()
        run_context = _make_ctx()
        run_context.total_cost = 0.50
        dispatcher = _make_dispatcher(run_context, session, tracker)
        dispatched = await dispatcher.dispatch({
            "event": "result",
            "data": {
                "session_id": "sess-abc",
                "total_cost_usd": 1.25,
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "num_turns": 3,
            },
        })

        assert run_context.total_cost == 1.75
        assert dispatched.result_data is not None
        assert dispatched.result_data["total_cost_usd"] == 1.25
        mock_db.save_session_id.assert_awaited_once_with("run-1", "sess-abc")
        mock_db.update_run_cost.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_subagent_start_calls_tracker(self, mock_db):
        """subagent_start event calls track_subagent_start."""
        session, tracker = _build_mocks()
        dispatcher = _make_dispatcher(_make_ctx(), session, tracker)
        dispatched = await dispatcher.dispatch({
            "event": "subagent_start",
            "data": {"agent_id": "a1", "agent_type": "builder"},
        })

        tracker.track_subagent_start.assert_called_once_with("a1", "builder")
        assert not dispatched.subagent_completed

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_subagent_stop_sets_completed_flag(self, mock_db):
        """subagent_stop returns subagent_completed=True."""
        session, tracker = _build_mocks()
        dispatcher = _make_dispatcher(_make_ctx(), session, tracker)
        dispatched = await dispatcher.dispatch({
            "event": "subagent_stop",
            "data": {"agent_id": "a1"},
        })

        tracker.track_subagent_stop.assert_called_once_with("a1")
        assert dispatched.subagent_completed is True

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_tool_use_calls_tracker(self, mock_db):
        """tool_use event calls track_tool_use."""
        session, tracker = _build_mocks()
        dispatcher = _make_dispatcher(_make_ctx(), session, tracker)
        await dispatcher.dispatch({
            "event": "tool_use",
            "data": {"agent_id": "a1"},
        })

        tracker.track_tool_use.assert_called_once_with("a1")

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_end_session_marks_ended(self, mock_db):
        """end_session event calls mark_ended on SessionGate."""
        session, tracker = _build_mocks()
        dispatcher = _make_dispatcher(_make_ctx(), session, tracker)
        await dispatcher.dispatch({"event": "end_session", "data": {}})

        session.mark_ended.assert_called_once()

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_end_session_denied_just_logs(self, mock_db, caplog):
        """end_session_denied logs but does not mark session ended."""
        session, tracker = _build_mocks()
        dispatcher = _make_dispatcher(_make_ctx(), session, tracker)
        with caplog.at_level(logging.INFO, logger="core.dispatch"):
            await dispatcher.dispatch({"event": "end_session_denied", "data": {}})

        session.mark_ended.assert_not_called()
        assert "end_session denied" in caplog.text

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_session_error_logs_error(self, mock_db, caplog):
        """session_error event logs the error."""
        session, tracker = _build_mocks()
        dispatcher = _make_dispatcher(_make_ctx(), session, tracker)
        with caplog.at_level(logging.ERROR, logger="core.dispatch"):
            dispatched = await dispatcher.dispatch({
                "event": "session_error",
                "data": {"error": "boom"},
            })

        assert "boom" in caplog.text
        assert dispatched.result_data is None

    @pytest.mark.asyncio
    @patch("core.sse_dispatch.db", new_callable=MagicMock)
    async def test_subagent_start_without_agent_id_is_ignored(self, mock_db):
        """subagent_start with empty agent_id does not call tracker."""
        session, tracker = _build_mocks()
        dispatcher = _make_dispatcher(_make_ctx(), session, tracker)
        await dispatcher.dispatch({
            "event": "subagent_start",
            "data": {"agent_id": "", "agent_type": "builder"},
        })

        tracker.track_subagent_start.assert_not_called()
