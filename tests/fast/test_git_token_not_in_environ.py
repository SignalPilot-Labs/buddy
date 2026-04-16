"""Regression: set_git_token must NOT write to os.environ.

Verifies that the module-level holder in repo_env keeps secrets out of
the process environment, and that build_git_env builds correct per-subprocess
env dicts without contaminating os.environ.
"""

import os

import pytest

from handlers.repo_env import (
    build_git_env,
    clear_git_token,
    get_git_token,
    set_git_token,
)


@pytest.fixture(autouse=True)
def _clean_token() -> object:
    """Ensure module-level token is cleared before and after each test."""
    clear_git_token()
    yield
    clear_git_token()


class TestGitTokenNotInEnviron:
    """set_git_token must not leak into os.environ."""

    def test_set_token_does_not_modify_environ(self) -> None:
        """set_git_token must not add or change any os.environ entry."""
        snapshot_before = dict(os.environ)
        set_git_token("fake-token-123")
        snapshot_after = dict(os.environ)
        assert snapshot_before == snapshot_after, (
            "set_git_token() must not touch os.environ"
        )

    def test_set_token_accessible_via_getter(self) -> None:
        """set_git_token() stores the token in the module-level holder."""
        set_git_token("fake-token-123")
        assert get_git_token() == "fake-token-123"

    def test_clear_token_resets_to_none(self) -> None:
        """clear_git_token() resets the holder back to None."""
        set_git_token("fake-token-123")
        clear_git_token()
        assert get_git_token() is None

    def test_build_with_token_raises_when_unset(self) -> None:
        """build_git_env(with_token=True) must raise RuntimeError if no token is set."""
        with pytest.raises(RuntimeError, match="no token is set"):
            build_git_env(with_token=True)

    def test_build_with_token_injects_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """build_git_env(with_token=True) injects GIT_TOKEN and GH_TOKEN."""
        monkeypatch.setenv("AGENT_INTERNAL_SECRET", "should-be-stripped")
        set_git_token("real-token-xyz")
        env = build_git_env(with_token=True)
        assert env["GIT_TOKEN"] == "real-token-xyz"
        assert env["GH_TOKEN"] == "real-token-xyz"
        assert "AGENT_INTERNAL_SECRET" not in env

    def test_build_with_token_strips_all_secret_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """build_git_env strips every key in SECRET_ENV_KEYS except GIT_TOKEN/GH_TOKEN."""
        monkeypatch.setenv("AGENT_INTERNAL_SECRET", "secret1")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "secret2")
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "secret3")
        monkeypatch.setenv("FGAT_GIT_TOKEN", "secret4")
        set_git_token("token-abc")
        env = build_git_env(with_token=True)
        assert "AGENT_INTERNAL_SECRET" not in env
        assert "ANTHROPIC_API_KEY" not in env
        assert "CLAUDE_CODE_OAUTH_TOKEN" not in env
        assert "FGAT_GIT_TOKEN" not in env
        assert env["GIT_TOKEN"] == "token-abc"
        assert env["GH_TOKEN"] == "token-abc"

    def test_build_without_token_excludes_git_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """build_git_env(with_token=False) must not include GIT_TOKEN or GH_TOKEN."""
        monkeypatch.setenv("AGENT_INTERNAL_SECRET", "should-be-stripped")
        set_git_token("real-token-xyz")
        env = build_git_env(with_token=False)
        assert "GIT_TOKEN" not in env
        assert "GH_TOKEN" not in env
        assert "AGENT_INTERNAL_SECRET" not in env

    def test_environ_unchanged_after_build_with_token(self) -> None:
        """build_git_env(with_token=True) must not modify os.environ."""
        set_git_token("any-token")
        snapshot_before = dict(os.environ)
        build_git_env(with_token=True)
        snapshot_after = dict(os.environ)
        assert snapshot_before == snapshot_after, (
            "build_git_env() must not touch os.environ"
        )
