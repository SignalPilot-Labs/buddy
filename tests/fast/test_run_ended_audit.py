"""Tests for run_ended audit event emission across all exit paths.

The run_ended audit must fire in server.py's finally block so it appears
AFTER teardown (PR creation) in the event feed. It must cover:
- Normal completion (round loop returns "completed")
- Bootstrap failure (bootstrap_run raises before round loop)
- Sandbox crash (exception during round loop or teardown)
- Cancellation / kill (CancelledError)
"""

import os
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# server.py reads these at import time
os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

from server import AgentServer
from utils.models import ActiveRun
from utils.models_http import StartRequest


@dataclass
class FakeTimeLock:
    """Minimal TimeLock stub."""

    locked: bool = False

    def elapsed_minutes(self) -> float:
        return 4.9


@dataclass
class FakeBootstrap:
    """Minimal BootstrapResult stub."""

    run: MagicMock
    inbox: MagicMock
    time_lock: FakeTimeLock
    metadata: MagicMock
    reports: MagicMock
    archiver: MagicMock
    base_session_options: dict
    task: str = "fix bug"
    starting_round: int = 0


def _make_active_run(run_id: str) -> ActiveRun:
    return ActiveRun(
        run_id=run_id,
        status="starting",
    )


def _make_body() -> StartRequest:
    return StartRequest(
        max_budget_usd=0,
        github_repo="owner/repo",
        prompt="fix the bug",
        duration_minutes=30,
        env={"GIT_TOKEN": "ghp_fake"},
    )


def _make_bootstrap() -> FakeBootstrap:
    run_ctx = MagicMock()
    run_ctx.run_id = "run-1"
    run_ctx.skip_pr = False
    return FakeBootstrap(
        run=run_ctx,
        inbox=MagicMock(),
        time_lock=FakeTimeLock(),
        metadata=MagicMock(),
        reports=MagicMock(),
        archiver=MagicMock(),
        base_session_options={},
    )


class TestRunEndedAudit:
    """run_ended audit fires in finally block for all exit paths."""

    @pytest.fixture
    def audit_calls(self):
        """Collect all log_audit calls."""
        calls: list[tuple[str, str, dict]] = []

        async def fake_log_audit(run_id: str, event_type: str, details: dict | None) -> None:
            calls.append((run_id, event_type, details or {}))

        return calls, fake_log_audit

    @pytest.mark.asyncio
    async def test_normal_completion(self, audit_calls: tuple) -> None:
        calls, fake_audit = audit_calls
        bootstrap = _make_bootstrap()

        with (
            patch("server.SandboxPool") as MockPool,
            patch("server.bootstrap_run", return_value=bootstrap),
            patch("server.run_rounds", return_value="completed"),
            patch("server.finalize_run", new_callable=AsyncMock),
            patch("server.log_audit", side_effect=fake_audit),
        ):
            pool = MockPool.return_value
            pool.create = AsyncMock(return_value=MagicMock(close=AsyncMock()))
            pool.destroy = AsyncMock()

            srv = AgentServer.__new__(AgentServer)
            srv._pool = pool
            srv._exec_timeout = 300
            srv._health_timeout = 30
            srv._clone_timeout = 120

            active = _make_active_run("run-1")
            await srv.execute_run(active, _make_body())

        run_ended = [c for c in calls if c[1] == "run_ended"]
        assert len(run_ended) == 1
        assert run_ended[0][2]["status"] == "completed"
        assert run_ended[0][2]["elapsed_minutes"] == 4.9

    @pytest.mark.asyncio
    async def test_bootstrap_failure(self, audit_calls: tuple) -> None:
        calls, fake_audit = audit_calls

        with (
            patch("server.SandboxPool") as MockPool,
            patch("server.bootstrap_run", side_effect=RuntimeError("clone failed")),
            patch("server.log_audit", side_effect=fake_audit),
        ):
            pool = MockPool.return_value
            pool.create = AsyncMock(return_value=MagicMock(close=AsyncMock()))
            pool.destroy = AsyncMock()
            pool.get_sandbox_logs = AsyncMock(return_value=[])

            srv = AgentServer.__new__(AgentServer)
            srv._pool = pool
            srv._exec_timeout = 300
            srv._health_timeout = 30
            srv._clone_timeout = 120

            active = _make_active_run("run-2")
            with pytest.raises(RuntimeError, match="clone failed"):
                await srv.execute_run(active, _make_body())

        run_ended = [c for c in calls if c[1] == "run_ended"]
        assert len(run_ended) == 1
        # bootstrap is None, so elapsed_minutes is None
        assert run_ended[0][2]["elapsed_minutes"] is None

    @pytest.mark.asyncio
    async def test_sandbox_crash(self, audit_calls: tuple) -> None:
        calls, fake_audit = audit_calls
        bootstrap = _make_bootstrap()

        with (
            patch("server.SandboxPool") as MockPool,
            patch("server.bootstrap_run", return_value=bootstrap),
            patch("server.run_rounds", side_effect=RuntimeError("sandbox died")),
            patch("server.log_audit", side_effect=fake_audit),
        ):
            pool = MockPool.return_value
            pool.create = AsyncMock(return_value=MagicMock(close=AsyncMock()))
            pool.destroy = AsyncMock()
            pool.get_sandbox_logs = AsyncMock(return_value=["error: OOM killed"])

            srv = AgentServer.__new__(AgentServer)
            srv._pool = pool
            srv._exec_timeout = 300
            srv._health_timeout = 30
            srv._clone_timeout = 120

            active = _make_active_run("run-3")
            with pytest.raises(RuntimeError, match="sandbox died"):
                await srv.execute_run(active, _make_body())

        # Both sandbox_crash and run_ended should fire
        event_types = [c[1] for c in calls]
        assert "sandbox_crash" in event_types
        assert "run_ended" in event_types

        run_ended = [c for c in calls if c[1] == "run_ended"]
        assert run_ended[0][2]["elapsed_minutes"] == 4.9

        # run_ended must come AFTER sandbox_crash
        crash_idx = event_types.index("sandbox_crash")
        ended_idx = event_types.index("run_ended")
        assert ended_idx > crash_idx

    @pytest.mark.asyncio
    async def test_run_ended_always_last_audit(self, audit_calls: tuple) -> None:
        """run_ended must be the last audit event emitted."""
        calls, fake_audit = audit_calls
        bootstrap = _make_bootstrap()

        with (
            patch("server.SandboxPool") as MockPool,
            patch("server.bootstrap_run", return_value=bootstrap),
            patch("server.run_rounds", return_value="stopped"),
            patch("server.finalize_run", new_callable=AsyncMock),
            patch("server.log_audit", side_effect=fake_audit),
        ):
            pool = MockPool.return_value
            pool.create = AsyncMock(return_value=MagicMock(close=AsyncMock()))
            pool.destroy = AsyncMock()

            srv = AgentServer.__new__(AgentServer)
            srv._pool = pool
            srv._exec_timeout = 300
            srv._health_timeout = 30
            srv._clone_timeout = 120

            active = _make_active_run("run-4")
            await srv.execute_run(active, _make_body())

        assert calls[-1][1] == "run_ended"
        assert calls[-1][2]["status"] == "stopped"
