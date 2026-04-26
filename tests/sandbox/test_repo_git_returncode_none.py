"""Regression test for falsy returncode check in _run() in repo_git.

When asyncio.subprocess.Process.returncode is None after communicate()
(indeterminate state), _run() must return exit_code -1, not 0.
The old code used `proc.returncode or 0` which silently masked None as success.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handlers.repo_git import _run


class TestRepoGitReturncodeNone:
    """Regression: proc.returncode None must produce exit_code -1, not 0."""

    @pytest.mark.asyncio
    async def test_returncode_none_returns_minus_one(self) -> None:
        """When returncode is None after communicate(), exit_code must be -1."""
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.communicate = AsyncMock(return_value=(b"some output", b""))

        with patch(
            "handlers.repo_git.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=mock_proc),
        ):
            result = await _run(["git", "status"], cwd="/tmp", timeout=30)

        assert result.exit_code == -1

    @pytest.mark.asyncio
    async def test_returncode_zero_returns_zero(self) -> None:
        """When returncode is 0 (success), exit_code must be 0, not -1."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch(
            "handlers.repo_git.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=mock_proc),
        ):
            result = await _run(["git", "status"], cwd="/tmp", timeout=30)

        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_returncode_nonzero_returned_unchanged(self) -> None:
        """When returncode is nonzero, exit_code must reflect the actual code."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch(
            "handlers.repo_git.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=mock_proc),
        ):
            result = await _run(["git", "status"], cwd="/tmp", timeout=30)

        assert result.exit_code == 1
