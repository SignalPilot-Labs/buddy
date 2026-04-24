"""Regression test for off-by-one in session error retry logic.

Bug: round_handlers.py used `>=` to compare consecutive_session_errors against
session_error_max_retries(). This caused the Nth error (where N == max_retries)
to terminate instead of retrying, giving one fewer retry than configured.

Fix: change `>=` to `>` so the run terminates only when error count strictly
exceeds max_retries (i.e., at error count max_retries + 1).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.constants import RUN_STATUS_ERROR
from lifecycle.round_handlers import handle_session_error
from utils.constants import session_error_max_retries
from utils.models import RoundResult


def _mock_run(run_id: str = "abcd1234-0000-0000-0000-000000000000") -> MagicMock:
    """Create a mock RunContext."""
    run = MagicMock()
    run.run_id = run_id
    return run


def _session_error_result(error: str = "500 Internal Server Error") -> RoundResult:
    """Create a RoundResult with session_error status."""
    return RoundResult(status="session_error", session_id="sess-1", error=error)


class TestSessionErrorOffByOne:
    """handle_session_error allows exactly max_retries retries before giving up."""

    @pytest.mark.asyncio
    async def test_nth_error_still_retries(self) -> None:
        """Error count == max_retries should still retry, not terminate.

        With consecutive_session_errors = max_retries - 1, after increment
        count = max_retries. With `>`, this does NOT exceed max_retries,
        so the handler must sleep and return None (retry).
        """
        with (
            patch("lifecycle.round_handlers.log_audit", new_callable=AsyncMock),
            patch(
                "lifecycle.round_handlers.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep,
        ):
            terminal, error_count = await handle_session_error(
                result=_session_error_result(),
                round_number=3,
                run=_mock_run(),
                consecutive_session_errors=session_error_max_retries() - 1,
            )

        assert terminal is None, (
            f"Error #{session_error_max_retries()} should still retry (terminal must be None)"
        )
        assert error_count == session_error_max_retries()
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_one_beyond_max_retries_terminates(self) -> None:
        """Error count == max_retries + 1 should terminate with RUN_STATUS_ERROR.

        With consecutive_session_errors = max_retries, after increment
        count = max_retries + 1. With `>`, this exceeds max_retries,
        so the handler must return RUN_STATUS_ERROR without sleeping.
        """
        with (
            patch("lifecycle.round_handlers.log_audit", new_callable=AsyncMock),
            patch(
                "lifecycle.round_handlers.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep,
        ):
            terminal, error_count = await handle_session_error(
                result=_session_error_result("401 Unauthorized"),
                round_number=4,
                run=_mock_run(),
                consecutive_session_errors=session_error_max_retries(),
            )

        assert terminal == RUN_STATUS_ERROR, (
            f"Error #{session_error_max_retries() + 1} must terminate with RUN_STATUS_ERROR"
        )
        assert error_count == session_error_max_retries() + 1
        mock_sleep.assert_not_called()
