"""Regression tests for automatic session cleanup after task completion.

When Session.run() completes naturally (LLM finishes, emits session_end),
the session must be automatically removed from SessionManager._sessions
without requiring an explicit stop() call.
"""

import asyncio
import unittest.mock
from unittest.mock import MagicMock

import pytest

from session.manager import SessionManager


class TestSessionAutoCleanup:
    """Verify sessions are removed from the registry when their task completes."""

    @pytest.mark.asyncio
    async def test_session_removed_after_task_completes_normally(self) -> None:
        """Session must be removed from _sessions when its task completes normally."""

        async def _immediate_run() -> None:
            return

        mock_session = MagicMock()
        mock_session.run = _immediate_run
        mock_session.task = None

        manager = SessionManager()

        with unittest.mock.patch("session.manager.Session", return_value=mock_session):
            session_id = await manager.start({})

        # Task was created and assigned; await it to let it complete
        assert mock_session.task is not None
        await mock_session.task

        # Yield to allow the done_callback to fire
        await asyncio.sleep(0)

        assert session_id not in manager._sessions

    @pytest.mark.asyncio
    async def test_session_not_double_removed_if_stop_called(self) -> None:
        """Calling stop() before the task finishes must not raise when the callback fires."""

        async def _cancellable_coro() -> None:
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                raise

        task = asyncio.create_task(_cancellable_coro())
        # Yield so the coroutine starts and reaches its first await.
        await asyncio.sleep(0)

        mock_session = MagicMock()
        mock_session.task = task

        manager = SessionManager()
        manager._sessions["test-session"] = mock_session

        # Register the same done_callback that start() registers — simulates a started session
        def _on_task_done(t: asyncio.Task) -> None:
            manager._sessions.pop("test-session", None)

        task.add_done_callback(_on_task_done)

        # stop() removes from _sessions and cancels the task
        await manager.stop("test-session")

        assert "test-session" not in manager._sessions
        assert task.cancelled()

        # Yield to allow the done_callback to fire after cancellation
        await asyncio.sleep(0)

        # Still absent — pop was idempotent
        assert "test-session" not in manager._sessions
