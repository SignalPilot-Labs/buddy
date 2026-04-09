"""Tests for explicit repo targeting — PRs must go to the configured repo."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sandbox_manager.repo_ops import RepoOps


class TestCreatePrExplicitRepo:
    """create_pr must pass --repo to gh CLI and fail if repo is unset."""

    @pytest.mark.asyncio
    async def test_create_pr_passes_repo_flag(self):
        """gh pr create must include --repo owner/repo."""
        client = MagicMock()
        client.exec = AsyncMock()
        ops = RepoOps(client, {})
        ops._repo = "acme/widgets"
        ops._initialized = True

        with patch.object(ops, "run_gh", new_callable=AsyncMock) as mock_gh:
            mock_gh.return_value = "https://github.com/acme/widgets/pull/1"
            with patch.object(ops, "_find_existing_pr", new_callable=AsyncMock, return_value=None):
                with patch.object(ops, "_read_agent_pr", new_callable=AsyncMock, return_value=("title", "body")):
                    url = await ops.create_pr("feat/x", "run-1", "main", 30)

        assert url == "https://github.com/acme/widgets/pull/1"
        call_args = mock_gh.call_args[0][0]
        assert "--repo" in call_args
        repo_idx = call_args.index("--repo")
        assert call_args[repo_idx + 1] == "acme/widgets"

    @pytest.mark.asyncio
    async def test_create_pr_fails_without_repo(self):
        """create_pr must raise if _repo is empty."""
        client = MagicMock()
        ops = RepoOps(client, {})
        ops._repo = ""
        ops._initialized = True

        with pytest.raises(RuntimeError, match="repo not set"):
            await ops.create_pr("feat/x", "run-1", "main", 30)

    @pytest.mark.asyncio
    async def test_find_existing_pr_passes_repo_flag(self):
        """gh pr view must include --repo."""
        client = MagicMock()
        ops = RepoOps(client, {})
        ops._repo = "acme/widgets"
        ops._initialized = True

        with patch.object(ops, "run_gh", new_callable=AsyncMock) as mock_gh:
            mock_gh.return_value = "https://github.com/acme/widgets/pull/1"
            url = await ops._find_existing_pr("feat/x", 30)

        assert url == "https://github.com/acme/widgets/pull/1"
        call_args = mock_gh.call_args[0][0]
        assert "--repo" in call_args
        repo_idx = call_args.index("--repo")
        assert call_args[repo_idx + 1] == "acme/widgets"
