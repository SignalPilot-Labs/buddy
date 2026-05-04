"""Regression test: execute_run must not raise UnboundLocalError when pool.create fails.

Before the fix, sandbox was assigned outside the try block, so if pool.create
raised, sandbox was unbound when _cleanup_run tried to use it in the finally.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

from server import AgentServer
from utils.models import ActiveRun
from utils.models_http import StartRequest


def _make_active_run(run_id: str) -> ActiveRun:
    return ActiveRun(run_id=run_id, status="starting")


def _make_body() -> StartRequest:
    return StartRequest(
        max_budget_usd=0,
        github_repo="owner/repo",
        prompt="fix the bug",
        duration_minutes=30,
        env={"GIT_TOKEN": "ghp_fake"},
    )


class TestExecuteRunUnboundSandbox:
    """Pool.create failure must not cause UnboundLocalError; cleanup must still run."""

    @pytest.mark.asyncio
    async def test_pool_create_raises_calls_destroy(self) -> None:
        """When pool.create raises, pool.destroy must still be called."""
        with (
            patch("server.SandboxPool") as MockPool,
            patch("server.log_audit", new_callable=AsyncMock),
        ):
            pool = MockPool.return_value
            pool.create = AsyncMock(side_effect=TimeoutError("container start timed out"))
            pool.destroy = AsyncMock()
            pool.get_logs = AsyncMock(return_value=[])

            srv = AgentServer.__new__(AgentServer)
            srv._pool = pool
            srv._exec_timeout = 300
            srv._health_timeout = 30
            srv._clone_timeout = 120
            srv._sandbox_secret = "test-secret"

            active = _make_active_run("run-timeout")
            with pytest.raises(TimeoutError, match="container start timed out"):
                await srv.execute_run(active, _make_body())

        pool.destroy.assert_called_once_with("run-timeout")

    @pytest.mark.asyncio
    async def test_pool_create_raises_not_unbound_error(self) -> None:
        """The exception propagated must be the original TimeoutError, not UnboundLocalError."""
        with (
            patch("server.SandboxPool") as MockPool,
            patch("server.log_audit", new_callable=AsyncMock),
        ):
            pool = MockPool.return_value
            pool.create = AsyncMock(side_effect=TimeoutError("timed out"))
            pool.destroy = AsyncMock()
            pool.get_logs = AsyncMock(return_value=[])

            srv = AgentServer.__new__(AgentServer)
            srv._pool = pool
            srv._exec_timeout = 300
            srv._health_timeout = 30
            srv._clone_timeout = 120
            srv._sandbox_secret = "test-secret"

            active = _make_active_run("run-timeout-2")
            exc_type = None
            try:
                await srv.execute_run(active, _make_body())
            except Exception as e:
                exc_type = type(e)

        assert exc_type is TimeoutError, f"Expected TimeoutError but got {exc_type}"
