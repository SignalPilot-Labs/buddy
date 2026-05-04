"""Tests for session task done callback behavior.

After SSE consolidation, the done_callback marks the session as finished
but does NOT remove it from the registry — it stays readable for event
draining. The agent calls delete() explicitly after draining.
"""

import asyncio
import unittest.mock
from unittest.mock import MagicMock

import pytest

from session.manager import SessionManager


class TestSessionDoneCallback:
    """Verify done_callback marks sessions finished but keeps them readable."""

    @pytest.mark.asyncio
    async def test_session_stays_after_task_completes(self) -> None:
        """Session must stay in _sessions when task completes (marked finished)."""

        async def _immediate_run() -> None:
            return

        mock_session = MagicMock()
        mock_session.run = _immediate_run
        mock_session.task = None
        mock_session.finished = False

        manager = SessionManager()

        with unittest.mock.patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        assert mock_session.task is not None
        await mock_session.task

        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # Session stays — marked finished but not removed
        assert session_id in manager._sessions
        assert mock_session.finished is True
        # active_count excludes finished sessions
        assert manager.active_count() == 0

    @pytest.mark.asyncio
    async def test_delete_after_task_completes(self) -> None:
        """delete() removes the session after the task finishes."""

        async def _immediate_run() -> None:
            return

        mock_session = MagicMock()
        mock_session.run = _immediate_run
        mock_session.task = None
        mock_session.finished = False

        manager = SessionManager()

        with unittest.mock.patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        await mock_session.task
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        manager.delete(session_id)
        assert session_id not in manager._sessions

    @pytest.mark.asyncio
    async def test_stop_after_task_completes_is_safe(self) -> None:
        """Calling stop() after the task finishes must succeed without error."""

        async def _immediate_run() -> None:
            return

        mock_session = MagicMock()
        mock_session.run = _immediate_run
        mock_session.task = None
        mock_session.finished = False

        manager = SessionManager()

        with unittest.mock.patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        await mock_session.task
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # stop() should not raise even though task already finished
        await manager.stop(session_id)
        # Session still in registry until delete
        assert session_id in manager._sessions
