"""Regression tests for SessionManager finished-but-readable session behavior.

After SSE consolidation, sessions stay in _sessions after task completion
(marked as finished) so the agent can drain remaining events. They are only
removed by explicit delete().
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from session.manager import SessionManager


class TestSessionTaskDoneCleanup:
    """Verify finished sessions stay readable until explicit delete."""

    @pytest.mark.asyncio
    async def test_session_stays_after_natural_completion(self) -> None:
        """Session stays in _sessions when its task completes (marked finished)."""
        async def _returns_immediately() -> None:
            pass

        mock_session = MagicMock()
        mock_session.run = _returns_immediately
        mock_session.finished = False

        manager = SessionManager()

        with patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        assert session_id in manager._sessions

        # Two yields: one to run the task, one for the done callback to fire.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # Session stays — not removed on completion
        assert session_id in manager._sessions
        assert mock_session.finished is True

    @pytest.mark.asyncio
    async def test_active_count_decrements_on_completion(self) -> None:
        """active_count() goes from 1 to 0 when task finishes (but session stays)."""
        done_event = asyncio.Event()

        async def _set_and_return() -> None:
            done_event.set()

        mock_session = MagicMock()
        mock_session.run = _set_and_return
        mock_session.finished = False

        manager = SessionManager()

        with patch("session.manager.Session", return_value=mock_session):
            await manager.start({})

        assert manager.active_count() == 1

        await done_event.wait()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # active_count is 0 (task done), but session still in _sessions
        assert manager.active_count() == 0
        assert len(manager._sessions) == 1

    @pytest.mark.asyncio
    async def test_delete_removes_session(self) -> None:
        """delete() removes the session from _sessions."""
        async def _returns_immediately() -> None:
            pass

        mock_session = MagicMock()
        mock_session.run = _returns_immediately
        mock_session.finished = False

        manager = SessionManager()

        with patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        await asyncio.sleep(0)
        await asyncio.sleep(0)

        manager.delete(session_id)
        assert session_id not in manager._sessions

    @pytest.mark.asyncio
    async def test_session_stays_after_task_exception(self) -> None:
        """Session stays in _sessions even when its task raises."""
        async def _raises() -> None:
            raise RuntimeError("session exploded")

        mock_session = MagicMock()
        mock_session.run = _raises
        mock_session.finished = False

        manager = SessionManager()

        with patch("session.manager.Session", return_value=mock_session), \
             patch("session.manager.log"):
            session_id = await manager.start({})
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        assert session_id in manager._sessions
        assert mock_session.finished is True
