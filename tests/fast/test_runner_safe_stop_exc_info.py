"""Regression test for missing exc_info=True in RoundRunner._safe_stop.

When _safe_stop fails to stop the sandbox session, log.warning must include
exc_info=True so the full stack trace is captured. Without it, only the
exception message is logged, making diagnosis of network failures impossible.

Fix: add exc_info=True to log.warning in the except block of _safe_stop.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_session.runner import RoundRunner
from utils.models import RunContext
from utils.run_config import RunAgentConfig

_DEFAULT_RUN_CONFIG = RunAgentConfig(
    max_rounds=128,
    tool_call_timeout_sec=3600,
    session_idle_timeout_sec=120,
    subagent_idle_kill_sec=600,
)


def _make_run() -> RunContext:
    return RunContext(
        run_id="abcd1234-0000-0000-0000-000000000099",
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


def _make_runner() -> RoundRunner:
    return RoundRunner(
        sandbox=MagicMock(),
        run=_make_run(),
        inbox=MagicMock(),
        time_lock=MagicMock(),
        run_config=_DEFAULT_RUN_CONFIG,
    )


class TestRunnerSafeStopExcInfo:
    """_safe_stop must call log.warning with exc_info=True when stop fails."""

    @pytest.mark.asyncio
    async def test_safe_stop_logs_exc_info_on_failure(self) -> None:
        """When session stop raises, log.warning is called with exc_info=True."""
        runner = _make_runner()
        runner._sandbox.session.stop = AsyncMock(side_effect=RuntimeError("connection refused"))

        with patch("agent_session.runner.log") as mock_log:
            await runner._safe_stop("session-abc")

        mock_log.warning.assert_called_once()
        call_kwargs = mock_log.warning.call_args[1]
        assert call_kwargs.get("exc_info") is True, (
            "log.warning must be called with exc_info=True to preserve the stack trace"
        )
