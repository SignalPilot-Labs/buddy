"""Regression tests for SessionManager.stop() awaiting the cancelled task.

After task.cancel(), stop() must await the task so that the CancelledError
handler in Session.run() executes (emitting session_end) before the session
is garbage collected. After SSE consolidation, stop() does NOT remove the
session — it stays readable for event draining. Use delete() to remove.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from session.manager import SessionManager


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
    async def test_stop_reraises_unexpected_exception(self) -> None:
        """stop() must re-raise if task raises a non-CancelledError exception."""
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

        with pytest.raises(RuntimeError, match="unexpected error"):
            await manager.stop("test-session")

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
