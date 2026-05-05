"""Regression test: archive_round failure log.warning must include exc_info=True.

Bug: When archiver.archive_round() raised an exception, log.warning() was called
without exc_info=True, discarding the stack trace. Archive failures can cause data
loss on resume — the full traceback is needed for diagnosis.

Fix: Add exc_info=True to the log.warning() call in round_loop.py.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifecycle.round_loop import run_rounds
from user.inbox import UserInbox
from utils.models import BootstrapResult, RoundsMetadata, RunContext
from utils.run_config import RunAgentConfig


def _make_run() -> RunContext:
    return RunContext(
        run_id="test-run-0000-0000-0000-000000000000",
        agent_role="worker",
        github_repo="org/repo",
        branch_name="fix/test",
        base_branch="main",
        duration_minutes=60,
        total_cost=0,
        total_input_tokens=0,
        total_output_tokens=0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _make_run_config() -> RunAgentConfig:
    return RunAgentConfig(
        max_rounds=1,
        tool_call_timeout_sec=3600,
        session_idle_timeout_sec=120,
        subagent_idle_kill_sec=600,
    )


def _make_bootstrap(run: RunContext, run_config: RunAgentConfig) -> BootstrapResult:
    """Build a minimal BootstrapResult with archive_round wired to raise."""
    inbox = UserInbox()

    reports = MagicMock()
    reports.ensure_round_directory = AsyncMock()
    reports.list_round = AsyncMock(return_value=[])

    metadata_store = MagicMock()
    metadata_store.load = AsyncMock(return_value=RoundsMetadata())

    time_lock = MagicMock()
    time_lock.remaining_minutes = MagicMock(return_value=55.0)
    time_lock.is_expired = MagicMock(return_value=False)
    time_lock.grace_round_used = False

    archiver = MagicMock()
    archiver.archive_round = AsyncMock(side_effect=OSError("S3 upload failed"))

    return BootstrapResult(
        run=run,
        inbox=inbox,
        time_lock=time_lock,
        reports=reports,
        metadata=metadata_store,
        archiver=archiver,
        base_session_options={"model": "claude-3-5-sonnet-20241022"},
        task="Fix the bug",
        model="claude-3-5-sonnet-20241022",
        fallback_model=None,
        run_start_time=0.0,
        starting_round=0,
        run_config=run_config,
    )


class TestArchiveRoundExcInfo:
    """archive_round warning must carry exc_info=True so the stack trace is preserved."""

    @pytest.mark.asyncio
    async def test_warning_has_exc_info_when_archive_fails(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log.warning for archive_round failure must include exc_info so traceback is logged."""
        run = _make_run()
        run_config = _make_run_config()
        bootstrap = _make_bootstrap(run, run_config)
        sandbox = MagicMock()

        terminal_outcome = MagicMock()
        round_result = MagicMock()

        # Patch RoundRunner so runner.run() returns without a real SDK call,
        # and patch _handle_round_outcome to return a terminal so run_rounds exits.
        with (
            patch("lifecycle.round_loop.RoundRunner") as mock_runner_cls,
            patch("lifecycle.round_loop._handle_round_outcome", new_callable=AsyncMock) as mock_outcome,
            patch("lifecycle.round_loop.db.get_user_activity", new_callable=AsyncMock) as mock_db,
            patch("lifecycle.round_loop.reconcile_orphaned_agent_calls", new_callable=AsyncMock),
            patch("lifecycle.round_loop.build_round_system_prompt", return_value={"type": "default", "preset": "default"}),
            patch("lifecycle.round_loop.build_initial_prompt", return_value="Go"),
            patch("lifecycle.round_loop.build_agent_defs", return_value=[]),
            caplog.at_level(logging.WARNING, logger="lifecycle.round_loop"),
        ):
            mock_runner_instance = MagicMock()
            mock_runner_instance.run = AsyncMock(return_value=round_result)
            mock_runner_cls.return_value = mock_runner_instance
            mock_db.return_value = []
            mock_outcome.return_value = (terminal_outcome, 0)

            await run_rounds(
                sandbox=sandbox,
                bootstrap=bootstrap,

                host_mounts=None,
                user_env_keys=[],
            )

        warning_records = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "archive_round" in r.getMessage()
        ]
        assert warning_records, (
            "Expected a WARNING log record mentioning 'archive_round' when archive fails"
        )
        record = warning_records[0]
        assert record.exc_info is not None, (
            "log.warning for archive_round failure must be called with exc_info=True "
            "so the stack trace is preserved for diagnosis"
        )

    @pytest.mark.asyncio
    async def test_archive_failure_does_not_propagate(self) -> None:
        """archive_round exceptions must be caught — they should not abort the round loop."""
        run = _make_run()
        run_config = _make_run_config()
        bootstrap = _make_bootstrap(run, run_config)
        sandbox = MagicMock()

        terminal_outcome = MagicMock()
        round_result = MagicMock()

        with (
            patch("lifecycle.round_loop.RoundRunner") as mock_runner_cls,
            patch("lifecycle.round_loop._handle_round_outcome", new_callable=AsyncMock) as mock_outcome,
            patch("lifecycle.round_loop.db.get_user_activity", new_callable=AsyncMock) as mock_db,
            patch("lifecycle.round_loop.reconcile_orphaned_agent_calls", new_callable=AsyncMock),
            patch("lifecycle.round_loop.build_round_system_prompt", return_value={"type": "default", "preset": "default"}),
            patch("lifecycle.round_loop.build_initial_prompt", return_value="Go"),
            patch("lifecycle.round_loop.build_agent_defs", return_value=[]),
        ):
            mock_runner_instance = MagicMock()
            mock_runner_instance.run = AsyncMock(return_value=round_result)
            mock_runner_cls.return_value = mock_runner_instance
            mock_db.return_value = []
            mock_outcome.return_value = (terminal_outcome, 0)

            # Should not raise even though archive_round raises OSError
            result = await run_rounds(
                sandbox=sandbox,
                bootstrap=bootstrap,

                host_mounts=None,
                user_env_keys=[],
            )

        assert result == terminal_outcome  # type: ignore[comparison-overlap]
