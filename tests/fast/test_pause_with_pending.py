"""Regression test: pause with pending messages redirects instead of pausing.

When the user hits pause and there are queued inject messages, the agent
should interrupt the current work and deliver the messages — not pause
the run. Only pause when no pending messages exist.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from user.control import UserControl
from user.inbox import UserInbox
from utils.models import UserEvent


def _make_control() -> tuple[UserControl, UserInbox, MagicMock]:
    """Build a UserControl with a mock sandbox and real inbox."""
    sandbox = MagicMock()
    sandbox.session.interrupt = AsyncMock()
    sandbox.session.send_message = AsyncMock()
    inbox = UserInbox()
    control = UserControl(sandbox, "sess-1", inbox)
    return control, inbox, sandbox


class TestPauseWithPendingMessages:
    """Pause + pending messages = redirect, not pause."""

    @pytest.mark.asyncio
    async def test_pause_with_pending_redirects(self) -> None:
        control, inbox, sandbox = _make_control()
        inbox.queue_message("Please focus on the API instead")

        outcome = await control.handle(UserEvent(kind="pause", payload=""))

        assert outcome.kind == "continue"
        assert "redirect" in outcome.reason
        # Pending messages should have been flushed
        assert inbox.take_pending_messages() == []
        # Session should have been interrupted
        sandbox.session.interrupt.assert_called_once_with("sess-1")
        # Message should have been sent to session
        sandbox.session.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_without_pending_pauses_immediately(self) -> None:
        control, inbox, sandbox = _make_control()

        outcome = await control.handle(UserEvent(kind="pause", payload=""))

        assert outcome.kind == "break_pause"
        sandbox.session.interrupt.assert_called_once_with("sess-1")
        sandbox.session.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_with_multiple_pending_flushes_all(self) -> None:
        control, inbox, sandbox = _make_control()
        inbox.queue_message("First redirect")
        inbox.queue_message("Second redirect")

        outcome = await control.handle(UserEvent(kind="pause", payload=""))

        assert outcome.kind == "continue"
        assert sandbox.session.send_message.call_count == 2
        assert inbox.take_pending_messages() == []
