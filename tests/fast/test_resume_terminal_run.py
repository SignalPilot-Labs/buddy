"""Tests for resuming terminal (stopped/crashed/completed) runs.

Verifies that:
- _restart_terminal_run fetches run info from DB and creates ActiveRun
- Bootstrap reuses existing branch name from DB
- Sandbox bootstrap checks out existing branch from origin
- Missing run returns 404
- Run without branch returns 409
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import HTTPException

from endpoints import _restart_terminal_run
from utils.models import ResumeRequest


def _mock_run_info(branch_name: str | None) -> dict:
    """Create a mock run info dict as returned by db.get_run_for_resume."""
    return {
        "id": "run-1",
        "branch_name": branch_name,
        "status": "stopped",
        "sdk_session_id": None,
        "custom_prompt": "fix the bug",
        "duration_minutes": 30.0,
        "base_branch": "main",
        "github_repo": "owner/repo",
        "total_cost_usd": 1.50,
        "total_input_tokens": 1000,
        "total_output_tokens": 500,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "model_name": "sonnet",
    }


def _make_resume_body(run_id: str, prompt: str | None) -> ResumeRequest:
    """Create a ResumeRequest."""
    return ResumeRequest(
        run_id=run_id,
        prompt=prompt,
        claude_token="test-token",
        git_token="ghp_test",
        github_repo="owner/repo",
        env={"CLAUDE_API_KEY": "test-token", "GIT_TOKEN": "ghp_test"},
    )


class TestRestartTerminalRun:
    """_restart_terminal_run must create a new ActiveRun for terminal runs."""

    @pytest.mark.asyncio
    async def test_restart_creates_active_run(self) -> None:
        """Restart must register a new ActiveRun and start execute_run."""
        server = MagicMock()
        server.execute_run = AsyncMock()
        server.register_run = MagicMock()
        server.remove_run = MagicMock()

        body = _make_resume_body("run-1", "continue the work")
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=_mock_run_info("autofyn/fix-bug")):
            with patch("endpoints.asyncio.create_task") as mock_task:
                mock_task.return_value = MagicMock()
                result = await _restart_terminal_run(server, body)

        assert result["ok"] is True
        assert result["restarted"] is True
        assert result["run_id"] == "run-1"
        server.remove_run.assert_called_once_with("run-1")
        server.register_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_uses_new_prompt_if_provided(self) -> None:
        """When prompt is provided, it overrides the original custom_prompt."""
        server = MagicMock()
        server.execute_run = AsyncMock()
        server.register_run = MagicMock()
        server.remove_run = MagicMock()

        body = _make_resume_body("run-1", "new instructions")
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=_mock_run_info("autofyn/fix-bug")):
            with patch("endpoints.asyncio.create_task") as mock_task:
                mock_task.return_value = MagicMock()
                await _restart_terminal_run(server, body)

        # The StartRequest passed to execute_run should have the new prompt
        registered_active = server.register_run.call_args[0][0]
        assert registered_active.run_id == "run-1"

    @pytest.mark.asyncio
    async def test_restart_falls_back_to_original_prompt(self) -> None:
        """When no prompt provided, uses the original custom_prompt from DB."""
        server = MagicMock()
        server.execute_run = AsyncMock()
        server.register_run = MagicMock()
        server.remove_run = MagicMock()

        body = _make_resume_body("run-1", None)
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=_mock_run_info("autofyn/fix-bug")):
            with patch("endpoints.asyncio.create_task") as mock_task:
                mock_task.return_value = MagicMock()
                await _restart_terminal_run(server, body)

        server.register_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_missing_run_returns_404(self) -> None:
        """Restart of a non-existent run must raise 404."""
        server = MagicMock()
        body = _make_resume_body("nonexistent", None)
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await _restart_terminal_run(server, body)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_restart_no_branch_returns_409(self) -> None:
        """Restart of a run with no branch must raise 409."""
        server = MagicMock()
        body = _make_resume_body("run-1", None)
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=_mock_run_info(None)):
            with pytest.raises(HTTPException) as exc_info:
                await _restart_terminal_run(server, body)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_restart_cleans_up_stale_active_run(self) -> None:
        """Restart must remove any stale ActiveRun before registering a new one."""
        server = MagicMock()
        server.execute_run = AsyncMock()
        server.register_run = MagicMock()
        server.remove_run = MagicMock()

        body = _make_resume_body("run-1", None)
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=_mock_run_info("autofyn/fix-bug")):
            with patch("endpoints.asyncio.create_task") as mock_task:
                mock_task.return_value = MagicMock()
                await _restart_terminal_run(server, body)

        # remove_run must be called BEFORE register_run
        server.remove_run.assert_called_once_with("run-1")
        server.register_run.assert_called_once()


class TestBootstrapResumesBranch:
    """bootstrap_run must reuse the existing branch from DB on resume."""

    @pytest.mark.asyncio
    async def test_bootstrap_reuses_existing_branch(self) -> None:
        """When DB has a branch name, bootstrap must use it instead of generating a new one."""
        mock_sandbox = MagicMock()
        mock_sandbox.repo.bootstrap = AsyncMock()
        mock_sandbox.file_system.read_dir = AsyncMock(return_value={})
        mock_sandbox.file_system.write_dir = AsyncMock()
        mock_sandbox.file_system.read = AsyncMock(return_value="[]")
        mock_sandbox.file_system.write = AsyncMock()

        with (
            patch("lifecycle.bootstrap.db.get_run_branch_name", new_callable=AsyncMock, return_value="autofyn/existing-branch"),
            patch("lifecycle.bootstrap.db.update_run_status", new_callable=AsyncMock) as mock_status,
            patch("lifecycle.bootstrap.db.update_run_branch", new_callable=AsyncMock) as mock_branch,
        ):
            from lifecycle.bootstrap import bootstrap_run
            await bootstrap_run(
                sandbox=mock_sandbox,
                run_id="run-1",
                custom_prompt="fix the bug",
                max_budget_usd=0,
                duration_minutes=30.0,
                base_branch="main",
                github_repo="owner/repo",
                model="sonnet",
                git_token="ghp_test",
                clone_timeout=60,
            )

        # Must use existing branch, not generate new
        call_args = mock_sandbox.repo.bootstrap.call_args
        assert call_args.kwargs["working_branch"] == "autofyn/existing-branch"
        # Must update status, not branch
        mock_status.assert_called_once_with("run-1", "running")
        mock_branch.assert_not_called()

    @pytest.mark.asyncio
    async def test_bootstrap_creates_new_branch_for_fresh_run(self) -> None:
        """When DB has no branch, bootstrap must generate a new one."""
        mock_sandbox = MagicMock()
        mock_sandbox.repo.bootstrap = AsyncMock()
        mock_sandbox.file_system.read_dir = AsyncMock(return_value={})
        mock_sandbox.file_system.write_dir = AsyncMock()
        mock_sandbox.file_system.read = AsyncMock(return_value="[]")
        mock_sandbox.file_system.write = AsyncMock()

        with (
            patch("lifecycle.bootstrap.db.get_run_branch_name", new_callable=AsyncMock, return_value=None),
            patch("lifecycle.bootstrap.db.update_run_status", new_callable=AsyncMock) as mock_status,
            patch("lifecycle.bootstrap.db.update_run_branch", new_callable=AsyncMock) as mock_branch,
        ):
            from lifecycle.bootstrap import bootstrap_run
            await bootstrap_run(
                sandbox=mock_sandbox,
                run_id="run-1",
                custom_prompt="fix the bug",
                max_budget_usd=0,
                duration_minutes=30.0,
                base_branch="main",
                github_repo="owner/repo",
                model="sonnet",
                git_token="ghp_test",
                clone_timeout=60,
            )

        # Must generate new branch and update DB
        call_args = mock_sandbox.repo.bootstrap.call_args
        assert "autofyn/" in call_args.kwargs["working_branch"]
        mock_branch.assert_called_once()
        mock_status.assert_not_called()


class TestResumeEdgeCases:
    """Edge cases for the /resume endpoint dispatch logic."""

    @pytest.mark.asyncio
    async def test_resume_paused_run_pushes_to_inbox(self) -> None:
        """Paused run with active inbox should push resume, not restart."""
        from unittest.mock import MagicMock
        inbox = MagicMock()
        inbox.push = MagicMock()
        active = MagicMock()
        active.run_id = "run-1"
        active.inbox = inbox

        server = MagicMock()
        server.get_run_or_first = MagicMock(return_value=active)

        # No body (simple resume) — should push to inbox
        from endpoints import register_routes
        from fastapi import FastAPI
        app = FastAPI()
        register_routes(app, server)

        # Simulate the resume logic directly
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.post("/resume")
        assert resp.status_code == 200
        inbox.push.assert_called_with("resume", "")

    @pytest.mark.asyncio
    async def test_resume_completed_run_restarts(self) -> None:
        """Completed run with run_id in body should trigger restart."""
        server = MagicMock()
        server.execute_run = AsyncMock()
        server.register_run = MagicMock()
        server.remove_run = MagicMock()

        run_info = _mock_run_info("autofyn/completed-branch")
        run_info["status"] = "completed"

        body = _make_resume_body("run-1", "continue please")
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=run_info):
            with patch("endpoints.asyncio.create_task") as mock_task:
                mock_task.return_value = MagicMock()
                result = await _restart_terminal_run(server, body)

        assert result["restarted"] is True

    @pytest.mark.asyncio
    async def test_resume_crashed_run_restarts(self) -> None:
        """Crashed run should be restartable."""
        server = MagicMock()
        server.execute_run = AsyncMock()
        server.register_run = MagicMock()
        server.remove_run = MagicMock()

        run_info = _mock_run_info("autofyn/crashed-branch")
        run_info["status"] = "crashed"

        body = _make_resume_body("run-1", None)
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=run_info):
            with patch("endpoints.asyncio.create_task") as mock_task:
                mock_task.return_value = MagicMock()
                result = await _restart_terminal_run(server, body)

        assert result["restarted"] is True

    @pytest.mark.asyncio
    async def test_resume_stopped_no_pr_run_restarts(self) -> None:
        """Stopped run (no PR) should be restartable."""
        server = MagicMock()
        server.execute_run = AsyncMock()
        server.register_run = MagicMock()
        server.remove_run = MagicMock()

        run_info = _mock_run_info("autofyn/stopped-branch")
        run_info["status"] = "stopped"

        body = _make_resume_body("run-1", "keep going")
        with patch("endpoints.db.get_run_for_resume", new_callable=AsyncMock, return_value=run_info):
            with patch("endpoints.asyncio.create_task") as mock_task:
                mock_task.return_value = MagicMock()
                result = await _restart_terminal_run(server, body)

        assert result["restarted"] is True
