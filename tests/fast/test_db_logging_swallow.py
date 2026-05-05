"""Regression test: idempotent DB log functions must not crash the round.

Bug: log_tool_call_idempotent raised on DB errors, which propagated up
through the stream dispatcher, crashed the round with fatal_error, and
cascaded into an aclose() RuntimeError.

Fix: idempotent log functions catch Exception and log.error instead of
propagating. The event is lost but the run continues.
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from utils.db_logging import log_tool_call_idempotent, log_audit_idempotent


class TestDbLoggingSwallow:
    """Idempotent log functions swallow DB errors and log them."""

    @pytest.mark.asyncio
    async def test_tool_call_swallows_db_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """log_tool_call_idempotent must not raise on DB failure."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=RuntimeError("PG null byte"))

        mock_factory = lambda: mock_session  # noqa: E731

        with (
            patch("utils.db_logging.get_session_factory", return_value=mock_factory),
            caplog.at_level(logging.ERROR, logger="utils.db_logging"),
        ):
            # Must not raise
            await log_tool_call_idempotent(
                run_id="test-run",
                phase="post",
                tool_name="Bash",
                input_data=None,
                output_data={"stdout": "bad\x00data"},
                duration_ms=100,
                permitted=True,
                deny_reason=None,
                agent_role="security-reviewer",
                tool_use_id="tu-123",
                session_id="sess-1",
                agent_id="agent-1",
                idempotency_key="key-1",
            )

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "DB error must be logged"
        assert "test-run" in error_records[0].message

    @pytest.mark.asyncio
    async def test_audit_swallows_db_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """log_audit_idempotent must not raise on DB failure."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=RuntimeError("PG error"))

        mock_factory = lambda: mock_session  # noqa: E731

        with (
            patch("utils.db_logging.get_session_factory", return_value=mock_factory),
            caplog.at_level(logging.ERROR, logger="utils.db_logging"),
        ):
            await log_audit_idempotent(
                run_id="test-run",
                event_type="llm_text",
                details={"text": "hello"},
                idempotency_key="key-2",
            )

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "DB error must be logged"
        assert "test-run" in error_records[0].message
