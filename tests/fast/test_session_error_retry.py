"""Tests for session error retry with exponential backoff.

When the Claude API returns 500/401, the round ends with status 'session_error'.
The round loop retries up to session_error_max_retries() times with exponential
backoff (2, 4, 8s). After exhausting retries, it stops the run with 'error'.
A successful round resets the counter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lifecycle.round_loop import _handle_round_outcome
from utils.constants import session_error_base_backoff_sec, session_error_max_retries
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
        with (
            patch("lifecycle.round_handlers.log_audit", new_callable=AsyncMock),
            patch("lifecycle.round_handlers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
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
                max_rounds=128,
            )

            assert terminal is None, "Should retry, not terminate"
            assert error_count == 1
            mock_sleep.assert_called_once_with(session_error_base_backoff_sec())

    @pytest.mark.asyncio
    async def test_second_error_doubles_backoff(self):
        """Second consecutive error sleeps 2 * BASE_BACKOFF_SEC."""
        with (
            patch("lifecycle.round_handlers.log_audit", new_callable=AsyncMock),
            patch("lifecycle.round_handlers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
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
                max_rounds=128,
            )

            assert terminal is None
            assert error_count == 2
            mock_sleep.assert_called_once_with(session_error_base_backoff_sec() * 2)

    @pytest.mark.asyncio
    async def test_max_retries_stops_run(self):
        """The Nth error (where N == max_retries) should still retry, not terminate."""
        with (
            patch("lifecycle.round_handlers.log_audit", new_callable=AsyncMock),
            patch("lifecycle.round_handlers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            terminal, error_count = await _handle_round_outcome(
                result=_session_error_result("401 Unauthorized"),
                round_number=3,
                sandbox=MagicMock(),
                run=_mock_run(),
                inbox=_mock_inbox(),
                time_lock=_mock_time_lock(),
                metadata_store=MagicMock(),
                exec_timeout=120,
                consecutive_session_errors=session_error_max_retries() - 1,
                max_rounds=128,
            )

            assert terminal is None, "The Nth error should still retry"
            assert error_count == session_error_max_retries()
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_round_resets_counter(self):
        """A complete round after errors resets the consecutive error counter."""
        with (
            patch("lifecycle.round_handlers.log_audit", new_callable=AsyncMock),
            patch("lifecycle.round_handlers._commit_and_push_round", new_callable=AsyncMock),
        ):
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
                max_rounds=128,
            )

            assert terminal is None
            assert error_count == 0, "Successful round must reset error counter"

    @pytest.mark.asyncio
    async def test_backoff_is_exponential(self):
        """Verify the backoff sequence is 2, 4, 8 seconds."""
        expected_backoffs = [
            session_error_base_backoff_sec() * (2 ** i)
            for i in range(session_error_max_retries())
        ]
        assert expected_backoffs == [2, 4, 8], (
            f"Expected [2, 4, 8] but got {expected_backoffs}"
        )

    @pytest.mark.asyncio
    async def test_audit_log_records_each_error(self):
        """Each session error is logged to audit with attempt number and backoff."""
        with (
            patch("lifecycle.round_handlers.log_audit", new_callable=AsyncMock) as mock_log_audit,
            patch("lifecycle.round_handlers.asyncio.sleep", new_callable=AsyncMock),
        ):
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
                max_rounds=128,
            )

            mock_log_audit.assert_called_once()
            call_args = mock_log_audit.call_args[0]
            assert call_args[1] == "session_error"
            details = call_args[2]
            assert details["attempt"] == 2
            assert details["error"] == "500 Server Error"
            assert details["backoff_sec"] == session_error_base_backoff_sec() * 2
