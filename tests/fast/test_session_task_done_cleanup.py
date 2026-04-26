"""Regression tests for SessionManager._on_task_done removing sessions.

When Session.run() completes naturally (not via stop()), the done callback
must remove the session from _sessions — otherwise it leaks memory and counts
against MAX_CONCURRENT_SESSIONS forever.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from session.manager import SessionManager


def _make_mock_session(run_coro: AsyncMock) -> MagicMock:
    """Build a mock Session with a real-coroutine run() method."""
    mock_session = MagicMock()
    mock_session.run = run_coro
    mock_session.task = None
    return mock_session


class TestSessionTaskDoneCleanup:
    """Verify _on_task_done cleans up _sessions on natural completion."""

    @pytest.mark.asyncio
    async def test_session_removed_after_natural_completion(self) -> None:
        """Session is removed from _sessions when its task completes normally."""
        async def _returns_immediately() -> None:
            pass

        mock_session = MagicMock()
        mock_session.run = _returns_immediately

        manager = SessionManager()

        with patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        assert session_id in manager._sessions

        # Two yields: one to run the task, one for the done callback to fire.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert session_id not in manager._sessions

    @pytest.mark.asyncio
    async def test_session_removed_after_task_exception(self) -> None:
        """Session is removed from _sessions even when its task raises."""
        async def _raises() -> None:
            raise RuntimeError("session exploded")

        mock_session = MagicMock()
        mock_session.run = _raises

        manager = SessionManager()

        with patch("session.manager.Session", return_value=mock_session), \
             patch("session.manager.log") as mock_log:
            session_id = await manager.start({})
            # Two yields: one to run the task, one for the done callback to fire.
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        assert session_id not in manager._sessions
        mock_log.warning.assert_called()

    @pytest.mark.asyncio
    async def test_active_count_decrements_on_natural_completion(self) -> None:
        """active_count() must go from 1 to 0 after natural task completion."""
        done_event = asyncio.Event()

        async def _set_and_return() -> None:
            done_event.set()

        mock_session = MagicMock()
        mock_session.run = _set_and_return

        manager = SessionManager()

        with patch("session.manager.Session", return_value=mock_session):
            await manager.start({})

        assert manager.active_count() == 1

        await done_event.wait()
        # Two yields: one to run the task, one for the done callback to fire.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert manager.active_count() == 0
