"""Regression test: resume must pass host_mounts to the agent.

Bug: _resume_completed_run built the resume body without host_mounts. The agent's
ResumeRequest model had no host_mounts field either. Remote sandbox runs that were
resumed always lost their configured mounts — apptainer started without -B flags.

Fix: read_credentials now receives sandbox_id and loads the correct mounts key.
The resume body includes host_mounts. ResumeRequest and _restart_terminal_run
forward host_mounts into the StartRequest.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.models_http import ResumeRequest, StartRequest


SAMPLE_MOUNTS = [
    {"host_path": "/data/input", "container_path": "/home/agentuser/repo/data", "mode": "ro"},
]


class TestResumeRequestHostMounts:
    """ResumeRequest must accept and forward host_mounts."""

    def test_resume_request_accepts_host_mounts(self) -> None:
        """ResumeRequest must parse host_mounts without error."""
        req = ResumeRequest(
            run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            prompt="fix the bug",
            claude_token=None,
            git_token=None,
            github_repo="org/repo",
            env=None,
            host_mounts=SAMPLE_MOUNTS,
            sandbox_id="11111111-2222-3333-4444-555555555555",
        )
        assert req.host_mounts == SAMPLE_MOUNTS

    def test_resume_request_host_mounts_defaults_none(self) -> None:
        """host_mounts must default to None when not provided."""
        req = ResumeRequest(
            run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            prompt=None,
            claude_token=None,
            git_token=None,
            github_repo=None,
            env=None,
        )
        assert req.host_mounts is None


class TestRestartTerminalRunHostMounts:
    """_restart_terminal_run must thread host_mounts into StartRequest."""

    @pytest.mark.asyncio
    async def test_host_mounts_forwarded_to_start_request(self) -> None:
        """host_mounts from ResumeRequest must appear in the StartRequest passed to execute_run."""
        import asyncio

        from endpoints.control import _restart_terminal_run

        body = ResumeRequest(
            run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            prompt="fix the bug",
            claude_token="tok",
            git_token="git-tok",
            github_repo="org/repo",
            env={"GIT_TOKEN": "git-tok"},
            host_mounts=SAMPLE_MOUNTS,
            sandbox_id="11111111-2222-3333-4444-555555555555",
        )

        run_info = {
            "branch_name": "autofyn/test-branch",
            "custom_prompt": "original prompt",
            "github_repo": "org/repo",
            "model_name": "claude-opus-4-6",
            "base_branch": "main",
            "duration_minutes": 30.0,
        }

        server = MagicMock()
        server.pool.return_value.resolve_start_cmd = AsyncMock(return_value="docker run ...")
        server.remove_run = MagicMock()
        server.register_run = MagicMock()

        captured_start_body: list[StartRequest] = []
        execute_future: asyncio.Future[None] = asyncio.get_event_loop().create_future()

        async def fake_execute(active: MagicMock, start_body: StartRequest) -> None:
            captured_start_body.append(start_body)
            execute_future.set_result(None)

        server.execute_run = fake_execute

        with patch("endpoints.control.db") as mock_db:
            mock_db.get_run_for_resume = AsyncMock(return_value=run_info)
            result = await _restart_terminal_run(server, body)

        # execute_run is wrapped in create_task — give it a tick to run
        await execute_future

        assert result["ok"] is True
        assert len(captured_start_body) == 1
        assert captured_start_body[0].host_mounts == SAMPLE_MOUNTS
