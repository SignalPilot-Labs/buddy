"""F5: build_git_env returns git-isolation vars and strips GIT_CONFIG_* keys."""

import os
from unittest.mock import patch

import pytest

from handlers.repo_env import build_git_env, clear_git_token, set_git_token


class TestBuildGitEnvIsolation:
    """build_git_env must set isolation vars and strip attacker-injected config."""

    def setup_method(self) -> None:
        clear_git_token()

    def teardown_method(self) -> None:
        clear_git_token()

    def test_isolation_vars_set_with_token_true(self) -> None:
        set_git_token("test-token")
        env = build_git_env(with_token=True)
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert env["GIT_CONFIG_COUNT"] == "0"
        assert env["HOME"] == "/tmp/git-isolated"
        assert env["XDG_CONFIG_HOME"] == "/nonexistent"

    def test_isolation_vars_set_with_token_false(self) -> None:
        env = build_git_env(with_token=False)
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert env["GIT_CONFIG_COUNT"] == "0"
        assert env["HOME"] == "/tmp/git-isolated"
        assert env["XDG_CONFIG_HOME"] == "/nonexistent"

    def test_strips_git_config_key_prefix(self) -> None:
        with patch.dict(os.environ, {"GIT_CONFIG_KEY_0": "credential.helper"}, clear=False):
            env = build_git_env(with_token=False)
        assert "GIT_CONFIG_KEY_0" not in env

    def test_strips_git_config_value_prefix(self) -> None:
        with patch.dict(os.environ, {"GIT_CONFIG_VALUE_0": "evil"}, clear=False):
            env = build_git_env(with_token=False)
        assert "GIT_CONFIG_VALUE_0" not in env

    def test_strips_git_config_count(self) -> None:
        """GIT_CONFIG_COUNT from os.environ is stripped before isolation override."""
        with patch.dict(os.environ, {"GIT_CONFIG_COUNT": "5"}, clear=False):
            env = build_git_env(with_token=False)
        # The value is then set to "0" by the isolation override.
        assert env["GIT_CONFIG_COUNT"] == "0"

    def test_strips_git_ssh_command(self) -> None:
        with patch.dict(os.environ, {"GIT_SSH_COMMAND": "evil-ssh"}, clear=False):
            env = build_git_env(with_token=False)
        assert "GIT_SSH_COMMAND" not in env

    def test_strips_git_config_exact_key(self) -> None:
        with patch.dict(os.environ, {"GIT_CONFIG": "evil"}, clear=False):
            env = build_git_env(with_token=False)
        assert "GIT_CONFIG" not in env

    def test_token_injected_when_with_token_true(self) -> None:
        set_git_token("my-secret-token")
        env = build_git_env(with_token=True)
        assert env["GIT_TOKEN"] == "my-secret-token"
        assert env["GH_TOKEN"] == "my-secret-token"

    def test_token_absent_when_with_token_false(self) -> None:
        env = build_git_env(with_token=False)
        assert "GIT_TOKEN" not in env
        assert "GH_TOKEN" not in env

    def test_raises_when_with_token_true_no_token_set(self) -> None:
        with pytest.raises(RuntimeError, match="no token is set"):
            build_git_env(with_token=True)

    def test_strips_multiple_injected_keys(self) -> None:
        injected = {
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "evil",
            "GIT_SSH_COMMAND": "evil-ssh",
            "GIT_CONFIG": "evil-global",
        }
        with patch.dict(os.environ, injected, clear=False):
            env = build_git_env(with_token=False)
        for key in injected:
            assert key not in env, f"Expected {key} to be stripped"
