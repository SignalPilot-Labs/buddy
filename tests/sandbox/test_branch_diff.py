"""Tests for _branch_diff in sandbox.handlers.repo.

_branch_diff is the one place that owns 'working branch vs base' stats
for both teardown (persisted into run.diff_stats) and the live
/repo/diff/stats endpoint. Pins three things that matter:

1. Diffs against the base-point SHA captured at bootstrap — never against
   the live `origin/<base>` tip — so post-bootstrap movement on the base
   branch doesn't pollute the branch's diff.
2. Two-arg form (`git diff A B`) — not three-dot. Three-dot needs a
   merge base, which shallow fetches on force-updated bases destroy.
3. The numstat + name-status stitching — empty output, non-zero exit,
   and normal output all route correctly.
"""

from unittest.mock import AsyncMock

import pytest

from handlers import repo as repo_module
from models import CmdResult


# 40-char hex SHA — representative of what bootstrap captures.
BASE_SHA = "abc1234567890deadbeef1234567890abcdef123"


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
    async def test_diffs_against_base_sha_not_origin_tip(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [
            _cmd_result("10\t2\tsrc/main.py\n"),  # numstat
            _cmd_result("M\tsrc/main.py\n"),  # name-status
        ]
        await repo_module._branch_diff("feature", BASE_SHA, 30)
        calls = [c.args[0] for c in git_mock.call_args_list]
        assert calls == [
            ["diff", "--numstat", BASE_SHA, "feature"],
            ["diff", "--name-status", BASE_SHA, "feature"],
        ]
        # Specifically: no `origin/<anything>` ref. We diff the frozen SHA.
        for call in calls:
            for part in call:
                assert not part.startswith("origin/"), f"unexpected origin ref in {call}"

    @pytest.mark.asyncio
    async def test_no_fetch_call(self, git_mock: AsyncMock) -> None:
        # Fetching was needed when we diffed `origin/<base>` (had to be
        # fresh). With a frozen SHA already in the object DB we skip the
        # network round-trip entirely.
        git_mock.side_effect = [
            _cmd_result("10\t2\tsrc/main.py\n"),
            _cmd_result("M\tsrc/main.py\n"),
        ]
        await repo_module._branch_diff("feature", BASE_SHA, 30)
        calls = [c.args[0] for c in git_mock.call_args_list]
        assert all("fetch" not in call for call in calls)

    @pytest.mark.asyncio
    async def test_two_arg_form_no_triple_dot(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [
            _cmd_result("10\t2\tsrc/main.py\n"),
            _cmd_result("M\tsrc/main.py\n"),
        ]
        await repo_module._branch_diff("feature", BASE_SHA, 30)
        calls = [c.args[0] for c in git_mock.call_args_list]
        for call in calls:
            assert not any("..." in part for part in call), f"three-dot in {call}"


class TestBranchDiffOutputStitching:
    """Verify _branch_diff composes numstat + name-status correctly."""

    @pytest.mark.asyncio
    async def test_empty_numstat_returns_empty_list(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [_cmd_result("   \n")]  # whitespace-only
        assert await repo_module._branch_diff("feature", BASE_SHA, 30) == []

    @pytest.mark.asyncio
    async def test_numstat_nonzero_exit_returns_empty(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [_cmd_result("", exit_code=128, stderr="fatal: ...")]
        assert await repo_module._branch_diff("feature", BASE_SHA, 30) == []

    @pytest.mark.asyncio
    async def test_name_status_nonzero_exit_returns_empty(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [
            _cmd_result("10\t2\tsrc/main.py\n"),  # numstat ok
            _cmd_result("", exit_code=1),  # name-status fails
        ]
        assert await repo_module._branch_diff("feature", BASE_SHA, 30) == []

    @pytest.mark.asyncio
    async def test_full_parse_added_modified_deleted(self, git_mock: AsyncMock) -> None:
        git_mock.side_effect = [
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
        result = await repo_module._branch_diff("feature", BASE_SHA, 30)
        assert result == [
            {"path": "src/new.py", "added": 25, "removed": 0, "status": "added"},
            {"path": "src/main.py", "added": 10, "removed": 2, "status": "modified"},
            {"path": "src/gone.py", "added": 0, "removed": 5, "status": "deleted"},
        ]

    @pytest.mark.asyncio
    async def test_binary_file_dashes_parsed_as_zero(self, git_mock: AsyncMock) -> None:
        # Binary files show as "-\t-\tpath" in numstat.
        git_mock.side_effect = [
            _cmd_result("-\t-\tassets/logo.png\n"),
            _cmd_result("A\tassets/logo.png\n"),
        ]
        result = await repo_module._branch_diff("feature", BASE_SHA, 30)
        assert result == [
            {"path": "assets/logo.png", "added": 0, "removed": 0, "status": "added"},
        ]
