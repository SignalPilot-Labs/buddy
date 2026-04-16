"""Tests for _branch_diff in sandbox.handlers.repo.

_branch_diff is the one place that owns 'working branch vs base' stats
for both teardown (persisted into run.diff_stats) and the live
/repo/diff/stats endpoint. Pins two things that matter:

1. Two-arg diff form (`git diff A B`) — not three-dot. Three-dot needs
   a merge base, which shallow fetches on force-updated bases destroy.
2. The numstat + name-status stitching — empty output, non-zero exit,
   and normal output all route correctly.
"""

from unittest.mock import AsyncMock

import pytest

from handlers import repo as repo_module
from models import CmdResult


def _cmd_result(stdout: str, exit_code: int = 0, stderr: str = "") -> CmdResult:
    return CmdResult(stdout=stdout, stderr=stderr, exit_code=exit_code)


@pytest.fixture
def git_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace _git with an AsyncMock so tests drive its stdout/exit."""
    mock = AsyncMock()
    monkeypatch.setattr(repo_module, "_git", mock)
    return mock


class TestBranchDiffGitInvocation:
    """Verify the exact git commands _branch_diff issues."""

    @pytest.mark.asyncio
    async def test_uses_two_arg_diff_not_three_dot(self, git_mock: AsyncMock) -> None:
        # fetch, numstat, name-status → three calls in order.
        git_mock.side_effect = [
            _cmd_result(""),  # fetch
            _cmd_result("10\t2\tsrc/main.py\n"),  # numstat
            _cmd_result("M\tsrc/main.py\n"),  # name-status
        ]
        await repo_module._branch_diff("feature", "main", 30)
        calls = [c.args[0] for c in git_mock.call_args_list]
        # Fetch is shallow with the base.
        assert calls[0] == ["fetch", "origin", "main", "--depth", "1"]
        # Crucially: no "..." in the ref arguments — two-arg form.
        assert calls[1] == ["diff", "--numstat", "origin/main", "feature"]
        assert calls[2] == ["diff", "--name-status", "origin/main", "feature"]
        for call in calls[1:]:
            assert not any("..." in part for part in call), f"three-dot in {call}"


class TestBranchDiffOutputStitching:
    """Verify _branch_diff composes numstat + name-status correctly."""

    @pytest.mark.asyncio
    async def test_empty_numstat_returns_empty_list(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [
            _cmd_result(""),  # fetch
            _cmd_result("   \n"),  # numstat: whitespace-only
        ]
        assert await repo_module._branch_diff("feature", "main", 30) == []

    @pytest.mark.asyncio
    async def test_numstat_nonzero_exit_returns_empty(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [
            _cmd_result(""),  # fetch
            _cmd_result("", exit_code=128, stderr="fatal: ..."),  # numstat fails
        ]
        assert await repo_module._branch_diff("feature", "main", 30) == []

    @pytest.mark.asyncio
    async def test_name_status_nonzero_exit_returns_empty(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [
            _cmd_result(""),  # fetch
            _cmd_result("10\t2\tsrc/main.py\n"),  # numstat ok
            _cmd_result("", exit_code=1),  # name-status fails
        ]
        assert await repo_module._branch_diff("feature", "main", 30) == []

    @pytest.mark.asyncio
    async def test_full_parse_added_modified_deleted(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [
            _cmd_result(""),  # fetch
            _cmd_result(
                "25\t0\tsrc/new.py\n"
                "10\t2\tsrc/main.py\n"
                "0\t5\tsrc/gone.py\n"
            ),
            _cmd_result(
                "A\tsrc/new.py\n"
                "M\tsrc/main.py\n"
                "D\tsrc/gone.py\n"
            ),
        ]
        result = await repo_module._branch_diff("feature", "main", 30)
        assert result == [
            {"path": "src/new.py", "added": 25, "removed": 0, "status": "added"},
            {"path": "src/main.py", "added": 10, "removed": 2, "status": "modified"},
            {"path": "src/gone.py", "added": 0, "removed": 5, "status": "deleted"},
        ]

    @pytest.mark.asyncio
    async def test_binary_file_dashes_parsed_as_zero(self, git_mock: AsyncMock) -> None:
        # Binary files show as "-\t-\tpath" in numstat.
        git_mock.side_effect = [
            _cmd_result(""),
            _cmd_result("-\t-\tassets/logo.png\n"),
            _cmd_result("A\tassets/logo.png\n"),
        ]
        result = await repo_module._branch_diff("feature", "main", 30)
        assert result == [
            {"path": "assets/logo.png", "added": 0, "removed": 0, "status": "added"},
        ]
