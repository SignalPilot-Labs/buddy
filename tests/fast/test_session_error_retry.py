"""Tests for session error retry with exponential backoff.

When the Claude API returns 500/401, the round ends with status 'session_error'.
The round loop retries up to SESSION_ERROR_MAX_RETRIES times with exponential
backoff (2, 4, 8s). After exhausting retries, it stops the run with 'error'.
A successful round resets the counter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.constants import SESSION_ERROR_BASE_BACKOFF_SEC, SESSION_ERROR_MAX_RETRIES
from utils.models import RoundResult


def _mock_run(run_id: str = "abcd1234-0000-0000-0000-000000000000") -> MagicMock:
    """Create a mock RunContext."""
    run = MagicMock()
    run.run_id = run_id
    return run


def _mock_inbox() -> MagicMock:
    """Create a mock UserInbox."""
    inbox = MagicMock()
    inbox.has_stop = MagicMock(return_value=False)
    return inbox


def _mock_time_lock() -> MagicMock:
    """Create a mock TimeLock that is not expired."""
    lock = MagicMock()
    lock.is_expired = MagicMock(return_value=False)
    return lock


def _session_error_result(error: str = "500 Internal Server Error") -> RoundResult:
    """Create a RoundResult with session_error status."""
    return RoundResult(status="session_error", session_id="sess-1", error=error)


def _complete_result() -> RoundResult:
    """Create a RoundResult with complete status."""
    return RoundResult(status="complete", session_id="sess-1")


class TestSessionErrorRetry:
    """Session errors retry with exponential backoff, then give up."""

    @pytest.mark.asyncio
    async def test_first_error_retries_with_base_backoff(self):
        """First session error sleeps BASE_BACKOFF_SEC and returns None (retry)."""
        from lifecycle.round_loop import _handle_round_outcome

        with (
            patch("lifecycle.round_loop.db", new_callable=MagicMock) as mock_db,
            patch("lifecycle.round_loop.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_db.log_audit = AsyncMock()
            terminal, error_count = await _handle_round_outcome(
                result=_session_error_result(),
                round_number=1,
                sandbox=MagicMock(),
                run=_mock_run(),
                inbox=_mock_inbox(),
                time_lock=_mock_time_lock(),
                metadata_store=MagicMock(),
                exec_timeout=120,
                consecutive_session_errors=0,
            )

            assert terminal is None, "Should retry, not terminate"
            assert error_count == 1
            mock_sleep.assert_called_once_with(SESSION_ERROR_BASE_BACKOFF_SEC)

    @pytest.mark.asyncio
    async def test_second_error_doubles_backoff(self):
        """Second consecutive error sleeps 2 * BASE_BACKOFF_SEC."""
        from lifecycle.round_loop import _handle_round_outcome

        with (
            patch("lifecycle.round_loop.db", new_callable=MagicMock) as mock_db,
            patch("lifecycle.round_loop.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_db.log_audit = AsyncMock()
            terminal, error_count = await _handle_round_outcome(
                result=_session_error_result(),
                round_number=2,
                sandbox=MagicMock(),
                run=_mock_run(),
                inbox=_mock_inbox(),
                time_lock=_mock_time_lock(),
                metadata_store=MagicMock(),
                exec_timeout=120,
                consecutive_session_errors=1,
            )

            assert terminal is None
            assert error_count == 2
            mock_sleep.assert_called_once_with(SESSION_ERROR_BASE_BACKOFF_SEC * 2)

    @pytest.mark.asyncio
    async def test_max_retries_stops_run(self):
        """After MAX_RETRIES consecutive errors, return 'error' terminal status."""
        from lifecycle.round_loop import _handle_round_outcome

        with (
            patch("lifecycle.round_loop.db", new_callable=MagicMock) as mock_db,
            patch("lifecycle.round_loop.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_db.log_audit = AsyncMock()
            terminal, error_count = await _handle_round_outcome(
                result=_session_error_result("401 Unauthorized"),
                round_number=3,
                sandbox=MagicMock(),
                run=_mock_run(),
                inbox=_mock_inbox(),
                time_lock=_mock_time_lock(),
                metadata_store=MagicMock(),
                exec_timeout=120,
                consecutive_session_errors=SESSION_ERROR_MAX_RETRIES - 1,
            )

            assert terminal == "error", "Should give up after max retries"
            assert error_count == SESSION_ERROR_MAX_RETRIES
            mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_round_resets_counter(self):
        """A complete round after errors resets the consecutive error counter."""
        from lifecycle.round_loop import _handle_round_outcome

        with (
            patch("lifecycle.round_loop.db", new_callable=MagicMock) as mock_db,
            patch("lifecycle.round_loop._commit_and_push_round", new_callable=AsyncMock),
        ):
            mock_db.log_audit = AsyncMock()
            terminal, error_count = await _handle_round_outcome(
                result=_complete_result(),
                round_number=4,
                sandbox=MagicMock(),
                run=_mock_run(),
                inbox=_mock_inbox(),
                time_lock=_mock_time_lock(),
                metadata_store=MagicMock(),
                exec_timeout=120,
                consecutive_session_errors=2,
            )

            assert terminal is None
            assert error_count == 0, "Successful round must reset error counter"

    @pytest.mark.asyncio
    async def test_backoff_is_exponential(self):
        """Verify the backoff sequence is 2, 4, 8 seconds."""
        from lifecycle.round_loop import _handle_round_outcome

        expected_backoffs = [
            SESSION_ERROR_BASE_BACKOFF_SEC * (2 ** i)
            for i in range(SESSION_ERROR_MAX_RETRIES)
        ]
        assert expected_backoffs == [2, 4, 8], (
            f"Expected [2, 4, 8] but got {expected_backoffs}"
        )

    @pytest.mark.asyncio
    async def test_audit_log_records_each_error(self):
        """Each session error is logged to audit with attempt number and backoff."""
        from lifecycle.round_loop import _handle_round_outcome

        with (
            patch("lifecycle.round_loop.db", new_callable=MagicMock) as mock_db,
            patch("lifecycle.round_loop.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_db.log_audit = AsyncMock()
            await _handle_round_outcome(
                result=_session_error_result("500 Server Error"),
                round_number=5,
                sandbox=MagicMock(),
                run=_mock_run(),
                inbox=_mock_inbox(),
                time_lock=_mock_time_lock(),
                metadata_store=MagicMock(),
                exec_timeout=120,
                consecutive_session_errors=1,
            )

            mock_db.log_audit.assert_called_once()
            call_args = mock_db.log_audit.call_args[0]
            assert call_args[1] == "session_error"
            details = call_args[2]
            assert details["attempt"] == 2
            assert details["error"] == "500 Server Error"
            assert details["backoff_sec"] == SESSION_ERROR_BASE_BACKOFF_SEC * 2
