"""Tests for RepoOps reading credentials from injected env, not os.environ."""

import os
from unittest.mock import AsyncMock, patch

from sandbox_manager.repo_ops import RepoOps


class TestRepoOpsEnv:
    """RepoOps must use the injected env dict, never os.environ."""

    def test_auth_env_uses_injected_env(self) -> None:
        client = AsyncMock()
        env = {"GIT_TOKEN": "ghp_test123"}
        ops = RepoOps(client, env)
        result = ops._auth_env()
        assert result["GH_TOKEN"] == "ghp_test123"

    def test_auth_env_ignores_os_environ(self) -> None:
        client = AsyncMock()
        env: dict[str, str] = {}
        ops = RepoOps(client, env)
        with patch.dict(os.environ, {"GIT_TOKEN": "from_os_environ"}):
            try:
                ops._auth_env()
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "GIT_TOKEN is not set" in str(e)

    def test_auth_env_raises_without_token(self) -> None:
        client = AsyncMock()
        env: dict[str, str] = {}
        ops = RepoOps(client, env)
        try:
            ops._auth_env()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "GIT_TOKEN is not set" in str(e)
