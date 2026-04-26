"""Tests for session task done callback behavior.

The done_callback logs task completion but does NOT remove the session from
the registry. Only stop() removes sessions — this prevents races where the
session disappears before the agent calls stop().
"""

import asyncio
import unittest.mock
from unittest.mock import MagicMock

import pytest

from session.manager import SessionManager


class TestSessionDoneCallback:
    """Verify done_callback does not auto-remove sessions."""

    @pytest.mark.asyncio
    async def test_session_stays_in_registry_after_task_completes(self) -> None:
        """Session must remain in _sessions after task completes — only stop() removes it."""

        async def _immediate_run() -> None:
            return

        mock_session = MagicMock()
        mock_session.run = _immediate_run
        mock_session.task = None

        manager = SessionManager()

        with unittest.mock.patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        assert mock_session.task is not None
        await mock_session.task

        # Yield to allow the done_callback to fire
        await asyncio.sleep(0)

        # Session must still be in registry — done_callback only logs
        assert session_id in manager._sessions

        # Explicit stop removes it
        await manager.stop(session_id)
        assert session_id not in manager._sessions

    @pytest.mark.asyncio
    async def test_stop_after_task_completes_is_safe(self) -> None:
        """Calling stop() after the task finishes must succeed without error."""

        async def _immediate_run() -> None:
            return

        mock_session = MagicMock()
        mock_session.run = _immediate_run
        mock_session.task = None

        manager = SessionManager()

        with unittest.mock.patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        await mock_session.task
        await asyncio.sleep(0)

        # stop() should not raise even though task already completed
        await manager.stop(session_id)
        assert session_id not in manager._sessions
