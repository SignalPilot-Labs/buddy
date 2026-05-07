"""Tests for resume passing start_cmd through to StartRequest.

Verifies that _restart_terminal_run resolves start_cmd via
server.pool().resolve_start_cmd() and passes it to StartRequest.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from endpoints.control import _restart_terminal_run
from tests.fast.helpers import make_server
from utils.models_http import ResumeRequest


def _mock_run_info() -> dict:
    """Create a mock run info dict as returned by db.get_run_for_resume."""
    return {
        "id": "run-1",
        "branch_name": "autofyn/fix-bug",
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
        "model_name": "claude-sonnet-4-6",
    }


class TestResumeStartCmd:
    """Resume must resolve start_cmd and pass it to execute_run."""

    @pytest.mark.asyncio
    async def test_resume_local_docker_resolves_start_cmd(self) -> None:
        """Resume with sandbox_id=None must resolve local Docker default."""
        server = make_server()
        mock_resolve = AsyncMock(return_value="docker run --rm=false ...")
        server.pool.return_value.resolve_start_cmd = mock_resolve

        body = ResumeRequest(
            run_id="run-1",
            prompt="continue",
            claude_token="tok",
            git_token="ghp_test",
            github_repo="owner/repo",
            env={"CLAUDE_API_KEY": "tok", "GIT_TOKEN": "ghp_test"},
            sandbox_id=None,
        )
        with (
            patch("endpoints.control.db.get_run_for_resume", new_callable=AsyncMock, return_value=_mock_run_info()),
            patch("endpoints.control.asyncio.create_task") as mock_task,
        ):
            mock_task.return_value = MagicMock()
            result = await _restart_terminal_run(server, body)

        assert result["restarted"] is True
        mock_resolve.assert_awaited_once_with(None)

    @pytest.mark.asyncio
    async def test_resume_remote_sandbox_resolves_start_cmd(self) -> None:
        """Resume with sandbox_id must resolve from sandbox config."""
        server = make_server()
        mock_resolve = AsyncMock(return_value="srun --partition=gpu my.sif")
        server.pool.return_value.resolve_start_cmd = mock_resolve

        body = ResumeRequest(
            run_id="run-1",
            prompt="continue",
            claude_token="tok",
            git_token="ghp_test",
            github_repo="owner/repo",
            env={"CLAUDE_API_KEY": "tok", "GIT_TOKEN": "ghp_test"},
            sandbox_id="sandbox-uuid",
        )
        with (
            patch("endpoints.control.db.get_run_for_resume", new_callable=AsyncMock, return_value=_mock_run_info()),
            patch("endpoints.control.asyncio.create_task") as mock_task,
        ):
            mock_task.return_value = MagicMock()
            result = await _restart_terminal_run(server, body)

        assert result["restarted"] is True
        mock_resolve.assert_awaited_once_with("sandbox-uuid")

    @pytest.mark.asyncio
    async def test_resume_passes_sandbox_id_to_start_request(self) -> None:
        """StartRequest built by resume must include sandbox_id."""
        server = make_server()

        body = ResumeRequest(
            run_id="run-1",
            prompt="continue",
            claude_token="tok",
            git_token="ghp_test",
            github_repo="owner/repo",
            env={"CLAUDE_API_KEY": "tok", "GIT_TOKEN": "ghp_test"},
            sandbox_id="sandbox-uuid",
        )
        with (
            patch("endpoints.control.db.get_run_for_resume", new_callable=AsyncMock, return_value=_mock_run_info()),
            patch("endpoints.control.asyncio.create_task") as mock_task,
        ):
            mock_task.return_value = MagicMock()
            await _restart_terminal_run(server, body)

        # execute_run receives the StartRequest as second arg
        start_req = server.execute_run.call_args[0][1]
        assert start_req.sandbox_id == "sandbox-uuid"
        assert start_req.start_cmd == "docker run test"
