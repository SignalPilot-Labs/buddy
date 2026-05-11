"""Regression test: git commit must always use --no-verify.

Target repos may have pre-commit hooks (secretlint, lint-staged, etc.)
that reject commits containing audit files, exploit PoCs, or homedir
paths. Since we develop on a branch and squash-merge via PR, the target
repo's CI validates the PR — commit hooks are irrelevant and must not
crash the run.
"""

import pytest
from unittest.mock import AsyncMock, patch

from models import CmdResult


# ── Helpers ──────────────────────────────────────────────────────────


def _ok(stdout: str = "") -> CmdResult:
    """Successful command result."""
    return CmdResult(stdout=stdout, stderr="", exit_code=0)


# ── Tests ────────────────────────────────────────────────────────────


class TestRepoServiceCommitNoVerify:
    """RepoService._commit must always pass --no-verify."""

    @pytest.mark.asyncio
    @patch("repo.service.REPO_WORK_DIR", "/fake/repo")
    @patch("repo.service.git", new_callable=AsyncMock)
    async def test_commit_always_passes_no_verify(
        self, mock_git: AsyncMock,
    ) -> None:
        """Every git commit must include --no-verify."""
        from repo.service import RepoService

        svc = RepoService()
        mock_git.side_effect = [_ok(), _ok()]

        await svc._commit("test msg")

        commit_call = mock_git.call_args_list[1]
        git_args = commit_call.args[0]
        assert "--no-verify" in git_args

    @pytest.mark.asyncio
    @patch("repo.service.REPO_WORK_DIR", "/fake/repo")
    @patch("repo.service.git", new_callable=AsyncMock)
    async def test_commit_success_returns_true(
        self, mock_git: AsyncMock,
    ) -> None:
        """Successful commit returns True."""
        from repo.service import RepoService

        svc = RepoService()
        mock_git.side_effect = [_ok(), _ok()]

        result = await svc._commit("test msg")

        assert result is True

    @pytest.mark.asyncio
    @patch("repo.service.REPO_WORK_DIR", "/fake/repo")
    @patch("repo.service.git", new_callable=AsyncMock)
    async def test_nothing_to_commit_returns_false(
        self, mock_git: AsyncMock,
    ) -> None:
        """When there's nothing to commit, returns False."""
        from repo.service import RepoService

        svc = RepoService()
        mock_git.side_effect = [
            _ok(),
            CmdResult(
                stdout="nothing to commit, working tree clean",
                stderr="",
                exit_code=1,
            ),
        ]

        result = await svc._commit("test msg")

        assert result is False
