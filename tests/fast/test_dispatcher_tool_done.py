"""Tests for StreamDispatcher: tool_done event handling."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.fast.conftest import _make_dispatcher


@pytest.fixture(autouse=True)
def _mock_db_writes():
    """Mock idempotent DB writes so dispatcher tests don't need a real DB."""
    with patch("agent_session.stream.log_tool_call_idempotent", new_callable=AsyncMock), \
         patch("agent_session.stream.log_audit_idempotent", new_callable=AsyncMock):
        yield


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
