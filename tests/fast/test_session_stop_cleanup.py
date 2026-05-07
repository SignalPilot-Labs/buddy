"""Regression tests for SessionManager.stop() awaiting the cancelled task.

After task.cancel(), stop() must await the task so that the CancelledError
handler in Session.run() executes (emitting session_end) before the session
is garbage collected. After SSE consolidation, stop() does NOT remove the
session — it stays readable for event draining. Use delete() to remove.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from sdk.manager import SessionManager


class TestSessionStopCleanup:
    """Verify stop() cancels and awaits the session task."""

    @pytest.mark.asyncio
    async def test_stop_cancels_and_awaits_task(self) -> None:
        """stop() must call task.cancel() and then await the task."""
        cancelled_error_raised = False

        async def _cancellable_coro() -> None:
            nonlocal cancelled_error_raised
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                cancelled_error_raised = True
                raise

        task = asyncio.create_task(_cancellable_coro())
        await asyncio.sleep(0)

        mock_session = MagicMock()
        mock_session.task = task
        mock_session.finished = False

        manager = SessionManager()
        manager._sessions["test-session"] = mock_session

        await manager.stop("test-session")

        assert task.cancelled()
        assert cancelled_error_raised
        # Session stays in registry (readable for event draining)
        assert "test-session" in manager._sessions

    @pytest.mark.asyncio
    async def test_stop_session_end_event_emitted_on_cancel(self) -> None:
        """The CancelledError handler in Session.run() must emit session_end."""
        events: list[dict] = []

        async def _run_with_cancel_handler() -> None:
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                events.append({"event": "session_end", "data": {"reason": "cancelled"}})
                raise

        task = asyncio.create_task(_run_with_cancel_handler())
        await asyncio.sleep(0)

        mock_session = MagicMock()
        mock_session.task = task
        mock_session.finished = False

        manager = SessionManager()
        manager._sessions["test-session"] = mock_session

        await manager.stop("test-session")

        assert any(e.get("event") == "session_end" for e in events)

    @pytest.mark.asyncio
    async def test_stop_logs_but_does_not_raise_unexpected_exception(self) -> None:
        """stop() must log and return cleanly when task raises a non-CancelledError exception."""
        async def _error_coro() -> None:
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                raise RuntimeError("unexpected error during cancellation")

        task = asyncio.create_task(_error_coro())
        await asyncio.sleep(0)

        mock_session = MagicMock()
        mock_session.task = task
        mock_session.finished = False

        manager = SessionManager()
        manager._sessions["test-session"] = mock_session

        # stop() must return cleanly — it is best-effort and should not propagate
        await manager.stop("test-session")

    @pytest.mark.asyncio
    async def test_stop_all_continues_after_session_exception(self) -> None:
        """stop_all() must clean up all sessions even if one raises during cancellation."""
        async def _error_coro() -> None:
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                raise RuntimeError("unexpected error during cancellation")

        async def _normal_coro() -> None:
            await asyncio.sleep(9999)

        error_task = asyncio.create_task(_error_coro())
        normal_task = asyncio.create_task(_normal_coro())
        await asyncio.sleep(0)

        error_session = MagicMock()
        error_session.task = error_task
        error_session.finished = False

        normal_session = MagicMock()
        normal_session.task = normal_task
        normal_session.finished = False

        manager = SessionManager()
        manager._sessions["error-session"] = error_session
        manager._sessions["normal-session"] = normal_session

        # stop_all() must complete without raising, even though error-session throws
        await manager.stop_all()

        # Both sessions must be deleted
        assert "error-session" not in manager._sessions
        assert "normal-session" not in manager._sessions

    @pytest.mark.asyncio
    async def test_delete_removes_session_from_registry(self) -> None:
        """delete() must remove the session from _sessions."""
        async def _simple_coro() -> None:
            await asyncio.sleep(9999)

        task = asyncio.create_task(_simple_coro())
        await asyncio.sleep(0)

        mock_session = MagicMock()
        mock_session.task = task
        mock_session.finished = False

        manager = SessionManager()
        manager._sessions["test-session"] = mock_session

        assert "test-session" in manager._sessions
        await manager.stop("test-session")
        # Still there after stop
        assert "test-session" in manager._sessions
        # Gone after delete
        manager.delete("test-session")
        assert "test-session" not in manager._sessions
