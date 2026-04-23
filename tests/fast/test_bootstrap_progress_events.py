"""Regression tests for bootstrap progress audit events.

Verifies that run_starting, sandbox_created, and repo_cloned audit events
are emitted at the correct points during the run lifecycle. These events
bridge the 5-10 second UX gap between clicking "Start" and seeing the
first run_started milestone in the dashboard feed.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# server.py reads secrets at import time — set before import.
os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer, app

from utils.constants import ENV_KEY_GIT_TOKEN, INTERNAL_SECRET_HEADER
from utils.models import ActiveRun, StartRequest


def _make_server() -> AgentServer:
    """Build an AgentServer instance without calling __init__."""
    srv = AgentServer.__new__(AgentServer)
    srv._pool = MagicMock()
    srv._exec_timeout = 300
    srv._health_timeout = 30
    srv._clone_timeout = 120
    return srv


def _make_body(sentinel_token: str) -> StartRequest:
    """Build a minimal StartRequest for testing."""
    return StartRequest(
        github_repo="owner/repo",
        prompt="fix the bug",
        duration_minutes=30,
        env={ENV_KEY_GIT_TOKEN: sentinel_token},
    )


class TestRunStartingEvent:
    """run_starting is emitted in the /start endpoint before the background task."""

    @pytest.mark.asyncio
    async def test_run_starting_emitted_on_start(self) -> None:
        """POST /start emits run_starting with repo before spawning task."""
        log_audit_calls: list[tuple[str, str, dict]] = []

        async def capture_log_audit(run_id: str, event_type: str, details: dict) -> None:
            log_audit_calls.append((run_id, event_type, details))

        from httpx import ASGITransport, AsyncClient

        with (
            patch("endpoints.db.create_run_starting", AsyncMock()),
            patch("endpoints.db.log_audit", side_effect=capture_log_audit),
            patch("server.AgentServer.execute_run", AsyncMock()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/start",
                    json={
                        "github_repo": "owner/repo",
                        "prompt": "fix it",
                        "duration_minutes": 30,
                        "git_token": "ghp_test",
                    },
                    headers={INTERNAL_SECRET_HEADER: "test-secret"},
                )

        assert resp.status_code == 200
        event_types = [call[1] for call in log_audit_calls]
        assert "run_starting" in event_types
        starting_call = next(c for c in log_audit_calls if c[1] == "run_starting")
        assert starting_call[2]["repo"] == "owner/repo"

    @pytest.mark.asyncio
    async def test_run_starting_emitted_before_task_spawn(self) -> None:
        """run_starting audit fires before asyncio.create_task."""
        call_order: list[str] = []

        async def capture_log_audit(run_id: str, event_type: str, details: dict) -> None:
            call_order.append(f"audit:{event_type}")

        def tracking_create_task(coro):
            call_order.append("create_task")
            # Cancel immediately so execute_run doesn't actually run
            task = MagicMock()
            task.add_done_callback = MagicMock()
            return task

        from httpx import ASGITransport, AsyncClient

        with (
            patch("endpoints.db.create_run_starting", AsyncMock()),
            patch("endpoints.db.log_audit", side_effect=capture_log_audit),
            patch("endpoints.asyncio.create_task", side_effect=tracking_create_task),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.post(
                    "/start",
                    json={
                        "github_repo": "owner/repo",
                        "prompt": "fix it",
                        "duration_minutes": 30,
                        "git_token": "ghp_test",
                    },
                    headers={INTERNAL_SECRET_HEADER: "test-secret"},
                )

        assert "audit:run_starting" in call_order
        assert "create_task" in call_order
        assert call_order.index("audit:run_starting") < call_order.index("create_task")


class TestSandboxReadyEvent:
    """sandbox_created is emitted immediately after pool.create() returns."""

    @pytest.mark.asyncio
    async def test_sandbox_created_emitted_after_pool_create(self) -> None:
        srv = _make_server()
        pool = srv._pool
        pool.create = AsyncMock(return_value=MagicMock(close=AsyncMock()))
        pool.destroy = AsyncMock()
        pool.get_sandbox_logs = AsyncMock(return_value=[])

        log_audit_calls: list[tuple[str, str, dict]] = []

        async def capture_log_audit(run_id: str, event_type: str, details: dict) -> None:
            log_audit_calls.append((run_id, event_type, details))

        with (
            patch("server.bootstrap_run", side_effect=RuntimeError("abort early")),
            patch("server.db.log_audit", side_effect=capture_log_audit),
        ):
            active = ActiveRun(run_id="run-progress", status="starting")
            with pytest.raises(RuntimeError, match="abort early"):
                await srv.execute_run(active, _make_body("ghp_test"))

        event_types = [call[1] for call in log_audit_calls]
        assert "sandbox_created" in event_types
        # sandbox_created must come before sandbox_crash (from the exception)
        sr_idx = event_types.index("sandbox_created")
        sc_idx = event_types.index("sandbox_crash")
        assert sr_idx < sc_idx

    @pytest.mark.asyncio
    async def test_sandbox_created_comes_before_bootstrap(self) -> None:
        """sandbox_created fires between pool.create and bootstrap_run."""
        call_order: list[str] = []

        async def mock_create(*args, **kwargs):
            call_order.append("pool.create")
            sandbox = MagicMock(close=AsyncMock())
            return sandbox

        async def mock_bootstrap(*args, **kwargs):
            call_order.append("bootstrap_run")
            raise RuntimeError("stop here")

        async def mock_log_audit(run_id: str, event_type: str, details: dict) -> None:
            call_order.append(f"audit:{event_type}")

        srv = _make_server()
        srv._pool.create = mock_create
        srv._pool.destroy = AsyncMock()
        srv._pool.get_sandbox_logs = AsyncMock(return_value=[])

        with (
            patch("server.bootstrap_run", side_effect=mock_bootstrap),
            patch("server.db.log_audit", side_effect=mock_log_audit),
        ):
            active = ActiveRun(run_id="run-order", status="starting")
            with pytest.raises(RuntimeError):
                await srv.execute_run(active, _make_body("ghp_test"))

        assert "pool.create" in call_order
        assert "audit:sandbox_created" in call_order
        create_idx = call_order.index("pool.create")
        ready_idx = call_order.index("audit:sandbox_created")
        assert ready_idx == create_idx + 1


class TestRepoClonedEvent:
    """repo_cloned is emitted after sandbox.repo.bootstrap() returns."""

    @pytest.mark.asyncio
    async def test_repo_cloned_emitted_during_bootstrap(self) -> None:
        """bootstrap_run emits repo_cloned with repo and branch details."""
        log_audit_calls: list[tuple[str, str, dict]] = []

        async def capture_log_audit(run_id: str, event_type: str, details: dict) -> None:
            log_audit_calls.append((run_id, event_type, details))

        mock_sandbox = MagicMock()
        mock_sandbox.repo.bootstrap = AsyncMock()
        mock_sandbox.file_system.read = AsyncMock(side_effect=Exception("no CLAUDE.md"))

        with (
            patch("lifecycle.bootstrap.db.log_audit", side_effect=capture_log_audit),
            patch("lifecycle.bootstrap.db.get_run_branch_name", AsyncMock(return_value=None)),
            patch("lifecycle.bootstrap.db.update_run_branch", AsyncMock()),
            patch("lifecycle.bootstrap.load_run_agent_config", AsyncMock(return_value=None)),
        ):
            from lifecycle.bootstrap import bootstrap_run
            with pytest.raises(Exception):
                await bootstrap_run(
                    sandbox=mock_sandbox,
                    run_id="run-clone",
                    custom_prompt="fix it",
                    max_budget_usd=5.0,
                    duration_minutes=30,
                    base_branch="main",
                    github_repo="owner/repo",
                    model="claude-opus-4-6",
                    effort="high",
                    git_token="ghp_test",
                    clone_timeout=120,
                )

        event_types = [call[1] for call in log_audit_calls]
        assert "repo_cloned" in event_types
        repo_call = next(c for c in log_audit_calls if c[1] == "repo_cloned")
        assert repo_call[2]["repo"] == "owner/repo"
        assert "branch" in repo_call[2]
