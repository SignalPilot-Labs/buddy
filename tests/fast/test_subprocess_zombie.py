"""Regression tests for zombie process cleanup after subprocess timeout.

Both execute.py and repo_git.py must call proc.wait() after proc.kill()
on timeout so the killed process is reaped and does not become a zombie.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.execute import handle_execute
from shared.subprocess import run_cmd


class TestSubprocessZombie:
    """Verify proc.wait() is called after proc.kill() on timeout."""

    @pytest.mark.asyncio
    async def test_execute_waits_after_kill_on_timeout(self) -> None:
        """handle_execute must await proc.wait() after proc.kill() on TimeoutError."""
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        async def fake_create_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
            return mock_proc

        request_body = {"args": ["sleep", "999"], "cwd": "/tmp", "timeout": 1}

        with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                mock_request = MagicMock()
                mock_request.json = AsyncMock(return_value=request_body)

                response = await handle_execute(mock_request)

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_awaited_once()
        assert response.status == 408

    @pytest.mark.asyncio
    async def test_repo_git_run_waits_after_kill_on_timeout(self) -> None:
        """_run in repo_git.py must await proc.wait() after proc.kill() on TimeoutError."""
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        async def fake_create_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                result = await run_cmd(["sleep", "999"], "/tmp", 1)

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_awaited_once()
        assert result.exit_code == -1
        assert result.stderr == "timed out"
