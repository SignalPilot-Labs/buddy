"""Tests for RepoOps reading credentials from injected env, not os.environ."""

import os
from unittest.mock import AsyncMock, patch

import pytest

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
            with pytest.raises(RuntimeError, match="GIT_TOKEN is not set"):
                ops._auth_env()

    def test_auth_env_raises_without_token(self) -> None:
        client = AsyncMock()
        env: dict[str, str] = {}
        ops = RepoOps(client, env)
        with pytest.raises(RuntimeError, match="GIT_TOKEN is not set"):
            ops._auth_env()
