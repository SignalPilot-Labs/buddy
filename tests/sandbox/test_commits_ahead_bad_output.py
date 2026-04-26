"""Regression test: _commits_ahead raises on non-integer git output.

Previously, corrupt rev-list output silently returned 0, which could
cause the orchestrator to skip PR creation. Now raises RuntimeError.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handlers.repo_git import _commits_ahead

TIMEOUT = 10


def _make_result(stdout: str, exit_code: int) -> MagicMock:
    """Build a fake _git result."""
    r = MagicMock()
    r.stdout = stdout
    r.exit_code = exit_code
    return r


class TestCommitsAheadBadOutput:
    """_commits_ahead must raise on non-integer output, not return 0."""

    @pytest.mark.asyncio
    async def test_garbage_output_raises(self) -> None:
        """Non-integer rev-list output must raise RuntimeError."""
        with patch(
            "handlers.repo_git._git",
            new_callable=AsyncMock,
            side_effect=[
                _make_result("", 0),   # fetch
                _make_result("not-a-number\n", 0),  # rev-list
            ],
        ):
            with patch("handlers.repo_git._fail"):
                with pytest.raises(RuntimeError, match="non-integer"):
                    await _commits_ahead("main", TIMEOUT)

    @pytest.mark.asyncio
    async def test_empty_output_raises(self) -> None:
        """Empty rev-list output must raise RuntimeError."""
        with patch(
            "handlers.repo_git._git",
            new_callable=AsyncMock,
            side_effect=[
                _make_result("", 0),
                _make_result("", 0),
            ],
        ):
            with patch("handlers.repo_git._fail"):
                with pytest.raises(RuntimeError, match="non-integer"):
                    await _commits_ahead("main", TIMEOUT)

    @pytest.mark.asyncio
    async def test_valid_count_returns_int(self) -> None:
        """Normal integer output must return the count."""
        with patch(
            "handlers.repo_git._git",
            new_callable=AsyncMock,
            side_effect=[
                _make_result("", 0),
                _make_result("5\n", 0),
            ],
        ):
            with patch("handlers.repo_git._fail"):
                result = await _commits_ahead("main", TIMEOUT)
        assert result == 5

    @pytest.mark.asyncio
    async def test_zero_count_returns_zero(self) -> None:
        """Zero is a valid count and must return 0."""
        with patch(
            "handlers.repo_git._git",
            new_callable=AsyncMock,
            side_effect=[
                _make_result("", 0),
                _make_result("0\n", 0),
            ],
        ):
            with patch("handlers.repo_git._fail"):
                result = await _commits_ahead("main", TIMEOUT)
        assert result == 0
