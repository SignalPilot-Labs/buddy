"""Regression test for AgentServer._runs memory leak on terminal runs.

Bug: _cleanup_run handled all terminal states (completed, crashed, killed,
stopped, error) but never removed the run from _runs. Terminal runs
accumulated indefinitely, growing _runs without bound.

Fix: _cleanup_run now calls self.remove_run(run_id) after destroying the
sandbox, so terminal runs are removed from the registry.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer

from utils.models import ActiveRun


def _make_server() -> AgentServer:
    """Build an AgentServer without calling __init__ (avoids DB + pool setup)."""
    srv = AgentServer.__new__(AgentServer)
    srv._pool = MagicMock()
    srv._runs = {}
    srv._pending_db_tasks = set()
    return srv


class TestServerTerminalRunRemoval:
    """_cleanup_run must remove terminal runs from _runs to prevent memory leak."""

    @pytest.mark.asyncio
    async def test_cleanup_run_removes_run_from_runs(self) -> None:
        """_cleanup_run must remove the run_id from _runs after cleanup."""
        srv = _make_server()
        srv._pool.destroy = AsyncMock()

        active = ActiveRun(run_id="run-terminal-1", status="crashed")
        srv._runs["run-terminal-1"] = active

        assert "run-terminal-1" in srv._runs

        with patch("server.log_audit", AsyncMock()):
            await srv._cleanup_run(
                run_id="run-terminal-1",
                active=active,
                terminal_status="crashed",
                bootstrap=None,
                sandbox=None,
            )

        assert "run-terminal-1" not in srv._runs

    @pytest.mark.asyncio
    async def test_cleanup_run_removes_run_after_pool_destroy_error(self) -> None:
        """_cleanup_run must still remove the run even if pool.destroy raises."""
        srv = _make_server()
        srv._pool.destroy = AsyncMock(side_effect=RuntimeError("destroy failed"))

        active = ActiveRun(run_id="run-terminal-2", status="completed")
        srv._runs["run-terminal-2"] = active

        with patch("server.log_audit", AsyncMock()):
            await srv._cleanup_run(
                run_id="run-terminal-2",
                active=active,
                terminal_status="completed",
                bootstrap=None,
                sandbox=None,
            )

        assert "run-terminal-2" not in srv._runs

    @pytest.mark.asyncio
    async def test_cleanup_run_removes_run_after_log_audit_error(self) -> None:
        """_cleanup_run must remove run even if log_audit raises."""
        srv = _make_server()
        srv._pool.destroy = AsyncMock()

        active = ActiveRun(run_id="run-terminal-3", status="killed")
        srv._runs["run-terminal-3"] = active

        with patch("server.log_audit", AsyncMock(side_effect=RuntimeError("audit failed"))):
            await srv._cleanup_run(
                run_id="run-terminal-3",
                active=active,
                terminal_status="killed",
                bootstrap=None,
                sandbox=None,
            )

        assert "run-terminal-3" not in srv._runs

    @pytest.mark.asyncio
    async def test_cleanup_run_is_idempotent_when_run_not_in_runs(self) -> None:
        """_cleanup_run must not raise if run_id is not in _runs (idempotent)."""
        srv = _make_server()
        srv._pool.destroy = AsyncMock()

        active = ActiveRun(run_id="run-terminal-4", status="stopped")
        # Deliberately NOT adding to _runs

        with patch("server.log_audit", AsyncMock()):
            await srv._cleanup_run(
                run_id="run-terminal-4",
                active=active,
                terminal_status="stopped",
                bootstrap=None,
                sandbox=None,
            )

        assert "run-terminal-4" not in srv._runs

    @pytest.mark.asyncio
    async def test_multiple_runs_only_target_removed(self) -> None:
        """_cleanup_run must only remove the target run, not other concurrent runs."""
        srv = _make_server()
        srv._pool.destroy = AsyncMock()

        active1 = ActiveRun(run_id="run-a", status="running")
        active2 = ActiveRun(run_id="run-b", status="crashed")
        srv._runs["run-a"] = active1
        srv._runs["run-b"] = active2

        with patch("server.log_audit", AsyncMock()):
            await srv._cleanup_run(
                run_id="run-b",
                active=active2,
                terminal_status="crashed",
                bootstrap=None,
                sandbox=None,
            )

        assert "run-a" in srv._runs
        assert "run-b" not in srv._runs
