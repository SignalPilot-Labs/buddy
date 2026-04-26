"""Regression test: _commits_ahead must handle multi-line git output.

Git sometimes prefixes output with warning lines (e.g. for shallow clones
or fsck notices). Before the fix, count_str.isdigit() would fail on the
full multi-line string even when the last line was a valid integer.

Fix: parse only the last non-empty line of stdout.
"""

from unittest.mock import AsyncMock, patch

import pytest

from handlers.repo_git import _commits_ahead
from models import CmdResult


def _make_result(stdout: str) -> CmdResult:
    return CmdResult(stdout=stdout, stderr="", exit_code=0)


class TestCommitsAheadMultiline:
    """_commits_ahead must parse last line of stdout and raise on empty/non-numeric output."""

    @pytest.mark.asyncio
    async def test_warning_prefix_returns_count(self) -> None:
        """Multi-line output with a warning prefix must return the integer on the last line."""
        fake_result = _make_result("warning: shallow clone detected\n5\n")

        with (
            patch("handlers.repo_git._git", new_callable=AsyncMock, return_value=fake_result),
            patch("handlers.repo_git._fail"),
        ):
            count = await _commits_ahead("main", 60)

        assert count == 5

    @pytest.mark.asyncio
    async def test_single_line_count(self) -> None:
        """Plain single-line output (no warning) must return the integer."""
        fake_result = _make_result("3")

        with (
            patch("handlers.repo_git._git", new_callable=AsyncMock, return_value=fake_result),
            patch("handlers.repo_git._fail"),
        ):
            count = await _commits_ahead("main", 60)

        assert count == 3

    @pytest.mark.asyncio
    async def test_empty_output_raises(self) -> None:
        """Empty stdout must raise RuntimeError, not silently return 0."""
        fake_result = _make_result("")

        with (
            patch("handlers.repo_git._git", new_callable=AsyncMock, return_value=fake_result),
            patch("handlers.repo_git._fail"),
        ):
            with pytest.raises(RuntimeError, match="empty output"):
                await _commits_ahead("main", 60)

    @pytest.mark.asyncio
    async def test_non_numeric_last_line_raises(self) -> None:
        """Non-numeric last line must raise RuntimeError."""
        fake_result = _make_result("not a number\n")

        with (
            patch("handlers.repo_git._git", new_callable=AsyncMock, return_value=fake_result),
            patch("handlers.repo_git._fail"),
        ):
            with pytest.raises(RuntimeError, match="non-integer output"):
                await _commits_ahead("main", 60)
