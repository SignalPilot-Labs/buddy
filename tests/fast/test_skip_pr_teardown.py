"""Tests for skip_pr flag threading through teardown.

Verifies that finalize_run skips PR creation when run.skip_pr is True,
and proceeds normally when skip_pr is False.
"""

import pytest
from unittest.mock import AsyncMock, patch

from lifecycle.teardown import finalize_run
from utils.models import RunContext, TeardownResult


def _make_run(skip_pr: bool) -> RunContext:
    """Create a RunContext with the given skip_pr flag."""
    return RunContext(
        run_id="run-1",
        agent_role="default",
        branch_name="feature-branch",
        base_branch="main",
        duration_minutes=30.0,
        github_repo="owner/repo",
        skip_pr=skip_pr,
    )


def _mock_teardown_result() -> TeardownResult:
    """Create a successful teardown result."""
    return TeardownResult(
        auto_committed=True,
        commits_ahead=3,
        pushed=True,
        push_error=None,
        pr_url="https://github.com/owner/repo/pull/1",
        pr_error=None,
        diff_stats=[{"file": "a.py", "additions": 10, "deletions": 2}],
    )


class TestSkipPrTeardown:
    """finalize_run must skip PR creation when run.skip_pr is True."""

    @pytest.mark.asyncio
    async def test_skip_pr_true_skips_teardown(self) -> None:
        """When skip_pr=True, _run_teardown must not be called."""
        run = _make_run(skip_pr=True)
        with (
            patch(
                "lifecycle.teardown._run_teardown", new_callable=AsyncMock
            ) as mock_teardown,
            patch("lifecycle.teardown._log_teardown_outcome", new_callable=AsyncMock),
            patch("lifecycle.teardown.db.finish_run", new_callable=AsyncMock),
        ):
            await finalize_run(
                sandbox=AsyncMock(),
                run=run,
                metadata_store=AsyncMock(),
                status="stopped",

            )
            mock_teardown.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_pr_false_runs_teardown(self) -> None:
        """When skip_pr=False, _run_teardown must be called."""
        run = _make_run(skip_pr=False)
        with (
            patch(
                "lifecycle.teardown._run_teardown",
                new_callable=AsyncMock,
                return_value=_mock_teardown_result(),
            ) as mock_teardown,
            patch("lifecycle.teardown._log_teardown_outcome", new_callable=AsyncMock),
            patch("lifecycle.teardown.db.finish_run", new_callable=AsyncMock),
        ):
            await finalize_run(
                sandbox=AsyncMock(),
                run=run,
                metadata_store=AsyncMock(),
                status="completed",

            )
            mock_teardown.assert_called_once()

    @pytest.mark.asyncio
    async def test_killed_status_skips_teardown_regardless(self) -> None:
        """Killed status skips teardown even if skip_pr is False."""
        run = _make_run(skip_pr=False)
        with (
            patch(
                "lifecycle.teardown._run_teardown", new_callable=AsyncMock
            ) as mock_teardown,
            patch("lifecycle.teardown._log_teardown_outcome", new_callable=AsyncMock),
            patch("lifecycle.teardown.db.finish_run", new_callable=AsyncMock),
        ):
            await finalize_run(
                sandbox=AsyncMock(),
                run=run,
                metadata_store=AsyncMock(),
                status="killed",

            )
            mock_teardown.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_pr_true_still_writes_db(self) -> None:
        """Even when skipping PR, finalize must still call finish_run."""
        run = _make_run(skip_pr=True)
        with (
            patch("lifecycle.teardown._run_teardown", new_callable=AsyncMock),
            patch("lifecycle.teardown._log_teardown_outcome", new_callable=AsyncMock),
            patch(
                "lifecycle.teardown.db.finish_run", new_callable=AsyncMock
            ) as mock_finish,
        ):
            await finalize_run(
                sandbox=AsyncMock(),
                run=run,
                metadata_store=AsyncMock(),
                status="stopped",

            )
            mock_finish.assert_called_once()
            args = mock_finish.call_args[0]
            assert args[0] == "run-1"
            assert args[1] == "stopped"
            assert args[2] is None  # no pr_url

    @pytest.mark.asyncio
    async def test_skip_pr_false_passes_pr_url_to_db(self) -> None:
        """When skip_pr=False and teardown succeeds, PR URL reaches finish_run."""
        run = _make_run(skip_pr=False)
        with (
            patch(
                "lifecycle.teardown._run_teardown",
                new_callable=AsyncMock,
                return_value=_mock_teardown_result(),
            ),
            patch("lifecycle.teardown._log_teardown_outcome", new_callable=AsyncMock),
            patch(
                "lifecycle.teardown.db.finish_run", new_callable=AsyncMock
            ) as mock_finish,
        ):
            await finalize_run(
                sandbox=AsyncMock(),
                run=run,
                metadata_store=AsyncMock(),
                status="completed",

            )
            args = mock_finish.call_args[0]
            assert args[2] == "https://github.com/owner/repo/pull/1"
