"""Regression test: stop with pending messages redirects instead of stopping.

When the user hits stop and there are queued inject messages, the agent
should interrupt the current subagent and deliver the messages — not
terminate the run. Only stop when no pending messages exist.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from user.control import UserControl
from user.inbox import UserInbox
from utils.models import UserEvent


def _make_control() -> tuple[UserControl, UserInbox, AsyncMock]:
    """Build a UserControl with a mock sandbox and real inbox."""
    sandbox = MagicMock()
    sandbox.session.interrupt = AsyncMock()
    sandbox.session.send_message = AsyncMock()
    inbox = UserInbox()
    control = UserControl(sandbox, "sess-1", inbox)
    return control, inbox, sandbox


class TestStopWithPendingMessages:
    """Stop + pending messages = redirect, not terminate."""

    @pytest.mark.asyncio
    async def test_stop_with_pending_redirects(self) -> None:
        control, inbox, sandbox = _make_control()
        inbox.queue_message("Please fix the tests instead")

        outcome = await control.handle(UserEvent(kind="stop", payload="user stop"))

        assert outcome.kind == "continue"
        assert "redirect" in outcome.reason
        assert not inbox.has_stop()
        # Pending messages should have been flushed
        assert inbox.take_pending_messages() == []
        # Session should have been interrupted
        sandbox.session.interrupt.assert_called_once_with("sess-1")
        # Message should have been sent to session
        sandbox.session.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_without_pending_stops(self) -> None:
        control, inbox, sandbox = _make_control()

        outcome = await control.handle(UserEvent(kind="stop", payload="user stop"))

        assert outcome.kind == "break_stop"
        assert inbox.has_stop()
        sandbox.session.interrupt.assert_called_once_with("sess-1")
        sandbox.session.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_with_multiple_pending_flushes_all(self) -> None:
        control, inbox, sandbox = _make_control()
        inbox.queue_message("First redirect")
        inbox.queue_message("Second redirect")

        outcome = await control.handle(UserEvent(kind="stop", payload="user stop"))

        assert outcome.kind == "continue"
        assert sandbox.session.send_message.call_count == 2
        assert inbox.take_pending_messages() == []
