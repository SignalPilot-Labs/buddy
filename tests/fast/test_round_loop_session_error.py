"""Regression test: session_error retries must not inflate round_number or create
junk archive directories.

Before the fix, run_rounds() incremented round_number unconditionally at the top
of the while loop and called archiver.archive_round() unconditionally after each
round — including session_error retries. On resume, archiver.restore_all() scans
disk directories and returns the highest round number, so junk directories from
session_error retries inflated the starting round on resume.

After the fix, when _handle_round_outcome returns (None, N) for a session_error
(i.e. max retries not yet exceeded), the loop decrements round_number and continues
without archiving. The next successful round re-uses the same round number.
"""

from typing import cast

import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch

from lifecycle.round_loop import run_rounds
from user.inbox import UserInbox
from utils.models import RoundResult, RoundStatus, RunContext, BootstrapResult, RoundsMetadata
from utils.run_config import RunAgentConfig
from db.constants import RUN_STATUS_COMPLETED


# ── Helpers ──────────────────────────────────────────────────────────


def _make_run() -> RunContext:
    return RunContext(
        run_id="abcd1234-0000-0000-0000-000000000000",
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
        max_rounds=128,
        tool_call_timeout_sec=3600,
        session_idle_timeout_sec=120,
        subagent_idle_kill_sec=600,
    )


def _make_bootstrap(run: RunContext, run_config: RunAgentConfig) -> BootstrapResult:
    """Build a minimal BootstrapResult with all async methods mocked."""
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
    archive_round_mock = AsyncMock()
    archiver.archive_round = archive_round_mock

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


def _make_round_result(status: RoundStatus) -> RoundResult:
    return RoundResult(status=status, session_id="sess-abc", error=None)


# ── Test class ────────────────────────────────────────────────────────


class TestRoundLoopSessionErrorRoundNumber:
    """Session error retries must not increment round_number or archive."""

    @pytest.mark.asyncio
    async def test_session_error_retries_do_not_inflate_round_number(self) -> None:
        """After 1 success + 2 session_errors + 1 final success, archive_round
        must be called with round numbers [1, 2] — not [1, 2, 3, 4]."""
        run = _make_run()
        run_config = _make_run_config()
        bootstrap = _make_bootstrap(run, run_config)
        sandbox = MagicMock()

        # Sequence of RoundResult objects that runner.run returns:
        #   round 1: complete (archives round 1)
        #   round 2 attempt 1: session_error → no archive, round_number stays 2
        #   round 2 attempt 2: session_error → no archive, round_number stays 2
        #   round 2 attempt 3: ended → archives round 2, loop terminates
        runner_results = [
            _make_round_result("complete"),
            _make_round_result("session_error"),
            _make_round_result("session_error"),
            _make_round_result("ended"),
        ]

        # _handle_round_outcome return values matching the above results:
        #   (None, 0)            — complete: continue
        #   (None, 1)            — session_error retry 1: no terminal
        #   (None, 2)            — session_error retry 2: no terminal
        #   (RUN_STATUS_COMPLETED, 0) — ended: terminate
        outcome_returns = [
            (None, 0),
            (None, 1),
            (None, 2),
            (RUN_STATUS_COMPLETED, 0),
        ]

        with (
            patch("lifecycle.round_loop.db.get_user_activity", new_callable=AsyncMock) as mock_db,
            patch("lifecycle.round_loop.reconcile_orphaned_agent_calls", new_callable=AsyncMock),
            patch("lifecycle.round_loop.build_round_system_prompt", return_value={"type": "text", "preset": "default"}),
            patch("lifecycle.round_loop.build_initial_prompt", return_value="start"),
            patch("lifecycle.round_loop.build_agent_defs", return_value=[]),
            patch("lifecycle.round_loop.RoundRunner") as MockRunner,
            patch("lifecycle.round_loop._handle_round_outcome", new_callable=AsyncMock) as mock_outcome,
        ):
            mock_db.return_value = []
            runner_instance = MockRunner.return_value
            runner_instance.run = AsyncMock(side_effect=runner_results)
            mock_outcome.side_effect = outcome_returns

            result = await run_rounds(
                sandbox=sandbox,
                bootstrap=bootstrap,

                host_mounts=None,
                user_env_keys=[],
            )

        assert result == RUN_STATUS_COMPLETED

        archive_mock = cast(AsyncMock, bootstrap.archiver.archive_round)
        archive_calls = archive_mock.call_args_list
        assert archive_calls == [call(1), call(2)], (
            f"Expected archive_round called with [1, 2], got {archive_calls}"
        )

    @pytest.mark.asyncio
    async def test_session_error_retries_do_not_create_junk_archives(self) -> None:
        """archive_round must NOT be called during session_error iterations.

        Specifically: 2 session_error retries must not produce any archive calls
        for those iterations. Only the successful round following the errors is
        archived, and it uses the same round number as the first session_error attempt.
        """
        run = _make_run()
        run_config = _make_run_config()
        bootstrap = _make_bootstrap(run, run_config)
        sandbox = MagicMock()

        # Single successful round followed by 2 session_errors and one final success.
        # The final success terminates the run.
        runner_results = [
            _make_round_result("complete"),
            _make_round_result("session_error"),
            _make_round_result("session_error"),
            _make_round_result("ended"),
        ]
        outcome_returns = [
            (None, 0),
            (None, 1),
            (None, 2),
            (RUN_STATUS_COMPLETED, 0),
        ]

        with (
            patch("lifecycle.round_loop.db.get_user_activity", new_callable=AsyncMock) as mock_db,
            patch("lifecycle.round_loop.reconcile_orphaned_agent_calls", new_callable=AsyncMock),
            patch("lifecycle.round_loop.build_round_system_prompt", return_value={"type": "text", "preset": "default"}),
            patch("lifecycle.round_loop.build_initial_prompt", return_value="start"),
            patch("lifecycle.round_loop.build_agent_defs", return_value=[]),
            patch("lifecycle.round_loop.RoundRunner") as MockRunner,
            patch("lifecycle.round_loop._handle_round_outcome", new_callable=AsyncMock) as mock_outcome,
        ):
            mock_db.return_value = []
            runner_instance = MockRunner.return_value
            runner_instance.run = AsyncMock(side_effect=runner_results)
            mock_outcome.side_effect = outcome_returns

            await run_rounds(
                sandbox=sandbox,
                bootstrap=bootstrap,

                host_mounts=None,
                user_env_keys=[],
            )

        # runner.run was called 4 times (1 success + 2 errors + 1 final)
        assert runner_instance.run.call_count == 4

        archive_mock = cast(AsyncMock, bootstrap.archiver.archive_round)
        assert archive_mock.call_count == 2

        archived_rounds = [
            c.args[0] for c in archive_mock.call_args_list
        ]
        assert archived_rounds == [1, 2], (
            f"Junk archive detected: expected [1, 2] but got {archived_rounds}"
        )
