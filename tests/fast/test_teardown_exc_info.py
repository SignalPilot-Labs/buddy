"""Regression test: teardown.py log.error must include exc_info=True.

Bug: When sandbox.repo.teardown() raises, log.error() was called without
exc_info=True, discarding the stack trace and making errors hard to diagnose.

Fix: Add exc_info=True to the log.error() call in _run_teardown.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from lifecycle.teardown import _run_teardown
from utils.models import RunContext


def _make_run() -> RunContext:
    return RunContext(
        run_id="run-teardown-exc-test",
        agent_role="default",
        branch_name="fix/branch",
        base_branch="main",
        duration_minutes=30.0,
        github_repo="owner/repo",
    )


class TestTeardownExcInfo:
    """_run_teardown must log with exc_info=True when sandbox.repo.teardown raises."""

    @pytest.mark.asyncio
    async def test_log_error_has_exc_info_on_teardown_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Stack trace must be attached when teardown raises an exception."""
        run = _make_run()
        sandbox = AsyncMock()
        sandbox.repo.teardown = AsyncMock(side_effect=RuntimeError("sandbox unreachable"))

        metadata_mock = AsyncMock()
        metadata_mock.load = AsyncMock(return_value=AsyncMock(
            pr_title="Test PR", rounds=[]
        ))

        with (
            patch("lifecycle.teardown.log_audit", new_callable=AsyncMock),
            caplog.at_level(logging.ERROR, logger="lifecycle.teardown"),
        ):
            result = await _run_teardown(
                sandbox=sandbox,
                run=run,
                metadata_store=metadata_mock,
                exec_timeout=60,
            )

        assert result is None
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "Expected at least one ERROR log record"
        record = error_records[0]
        assert record.exc_info is not None, (
            "log.error must be called with exc_info=True so the stack trace is preserved"
        )
