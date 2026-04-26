"""Tests for session task done callback behavior.

The done_callback removes the session from the registry automatically when
the task completes naturally. This prevents memory leaks and incorrect
MAX_CONCURRENT_SESSIONS counts when sessions end without an explicit stop().
"""

import asyncio
import unittest.mock
from unittest.mock import MagicMock

import pytest

from session.manager import SessionManager


class TestSessionDoneCallback:
    """Verify done_callback auto-removes sessions on natural completion."""

    @pytest.mark.asyncio
    async def test_session_removed_from_registry_after_task_completes(self) -> None:
        """Session must be removed from _sessions when task completes naturally."""

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

        # Two yields: one for the task, one for the done callback to fire.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # Session must be removed — done_callback pops it to avoid leaks.
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
        # Two yields so the done_callback fires and pops the session first.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # stop() should not raise even though session was already removed
        await manager.stop(session_id)
        assert session_id not in manager._sessions
