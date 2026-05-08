"""Regression test: pause/stop must not crash when session client is not ready.

Bug: When a pause arrives at the very start of a new round, the Claude SDK
client hasn't initialized yet (sandbox returns 503). The interrupt call in
_handle_pause raised SessionNotReadyError, which propagated as a fatal error
and killed the entire run.

Fix: _handle_pause and _handle_stop use _try_interrupt() which catches
SessionNotReadyError — there is nothing running to interrupt, so the
interrupt is a no-op, and pause/stop still succeed.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sandbox_client.handlers.session import SessionNotReadyError
from user.control import UserControl
from user.inbox import UserInbox
from utils.models import UserEvent


def _make_control_not_ready() -> tuple[UserControl, UserInbox, MagicMock]:
    """Build a UserControl whose sandbox returns 503 on interrupt."""
    sandbox = MagicMock()
    sandbox.session.interrupt = AsyncMock(
        side_effect=SessionNotReadyError("sess-1 client not ready"),
    )
    sandbox.session.send_message = AsyncMock()
    inbox = UserInbox()
    control = UserControl(sandbox, "sess-1", inbox)
    return control, inbox, sandbox


class TestPauseStopSessionNotReady:
    """Pause and stop must succeed even when session client is not ready."""

    @pytest.mark.asyncio
    async def test_pause_not_ready_returns_break_pause(self) -> None:
        """Pause on unready session must return break_pause, not raise."""
        control, inbox, sandbox = _make_control_not_ready()

        outcome = await control.handle(UserEvent(kind="pause", payload=""))

        assert outcome.kind == "break_pause"
        sandbox.session.interrupt.assert_called_once_with("sess-1")

    @pytest.mark.asyncio
    async def test_stop_not_ready_returns_break_stop(self) -> None:
        """Stop on unready session must return break_stop, not raise."""
        control, inbox, sandbox = _make_control_not_ready()

        outcome = await control.handle(UserEvent(kind="stop", payload="user stop"))

        assert outcome.kind == "break_stop"
        sandbox.session.interrupt.assert_called_once_with("sess-1")

    @pytest.mark.asyncio
    async def test_pause_with_pending_not_ready_redirects(self) -> None:
        """Pause with pending messages on unready session must redirect, not raise."""
        control, inbox, sandbox = _make_control_not_ready()
        inbox.queue_message("change direction")

        outcome = await control.handle(UserEvent(kind="pause", payload=""))

        assert outcome.kind == "continue"
        assert "redirect" in outcome.reason

    @pytest.mark.asyncio
    async def test_stop_with_pending_not_ready_redirects(self) -> None:
        """Stop with pending messages on unready session must redirect, not raise."""
        control, inbox, sandbox = _make_control_not_ready()
        inbox.queue_message("change direction")

        outcome = await control.handle(UserEvent(kind="stop", payload="user stop"))

        assert outcome.kind == "continue"
        assert "redirect" in outcome.reason
