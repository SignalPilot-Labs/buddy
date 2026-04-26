"""Regression test: DB error in get_user_activity must propagate, not be swallowed.

Before the fix, round_loop.py wrapped db.get_user_activity() in a try/except that
silently continued with user_activity=[] on any exception. This caused user messages
(already drained from the inbox at line 85) to be permanently lost.

After the fix, the call is bare — exceptions propagate to server.py's crash handler.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lifecycle.round_loop import run_rounds
from user.inbox import UserInbox
from utils.models import RunContext, BootstrapResult, RoundsMetadata
from utils.run_config import RunAgentConfig


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


class TestRoundLoopUserActivity:
    """DB errors from get_user_activity must propagate, not be swallowed."""

    @pytest.mark.asyncio
    async def test_db_error_propagates(self) -> None:
        """When db.get_user_activity raises, run_rounds must re-raise, not continue."""
        run = _make_run()
        run_config = _make_run_config()
        bootstrap = _make_bootstrap(run, run_config)
        sandbox = MagicMock()

        db_error = RuntimeError("DB connection refused")

        with patch("lifecycle.round_loop.db.get_user_activity", new_callable=AsyncMock) as mock_db:
            mock_db.side_effect = db_error
            with pytest.raises(RuntimeError, match="DB connection refused"):
                await run_rounds(
                    sandbox=sandbox,
                    bootstrap=bootstrap,
                    exec_timeout=120,
                    host_mounts=None,
                    user_env_keys=[],
                )

    @pytest.mark.asyncio
    async def test_db_error_not_swallowed_as_empty_activity(self) -> None:
        """Verify the exception is not caught internally — run_rounds does not return normally."""
        run = _make_run()
        run_config = _make_run_config()
        bootstrap = _make_bootstrap(run, run_config)
        sandbox = MagicMock()

        with patch("lifecycle.round_loop.db.get_user_activity", new_callable=AsyncMock) as mock_db:
            mock_db.side_effect = OSError("DB unavailable")
            raised = False
            try:
                await run_rounds(
                    sandbox=sandbox,
                    bootstrap=bootstrap,
                    exec_timeout=120,
                    host_mounts=None,
                    user_env_keys=[],
                )
            except OSError:
                raised = True

            assert raised, "run_rounds must propagate the DB exception, not swallow it"
