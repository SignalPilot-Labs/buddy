"""Regression: every repo.py subprocess must receive an explicit env= dict.

Verifies:
  - _install_git_credentials does not write to os.environ
  - git config call (auth-free) has env= set, GIT_TOKEN absent
  - _push env carries GIT_TOKEN and GH_TOKEN
  - _has_changes (git status) env has no token
  - _commits_ahead fetch call has GIT_TOKEN; rev-list call does not
  - No subprocess call's env contains AGENT_INTERNAL_SECRET
  - Non-git _run calls also have env= set (no secret env vars)
"""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers import repo_env
from handlers.repo_phases import _commits_ahead, _run
from handlers.repo import _install_git_credentials, _has_changes, _push


_FAKE_TOKEN = "fake-token-abc"
_SECRET_KEYS = {"AGENT_INTERNAL_SECRET", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "FGAT_GIT_TOKEN"}


def _make_fake_process() -> AsyncMock:
    """Return an AsyncMock that looks like a successful subprocess."""
    proc = AsyncMock()
    proc.returncode = 0
    proc.communicate = AsyncMock(return_value=(b"", b""))
    proc.kill = MagicMock()
    return proc


@pytest.fixture(autouse=True)
def _clean_token() -> object:
    """Clear the module-level token before/after each test."""
    repo_env.clear_git_token()
    yield
    repo_env.clear_git_token()


class TestGitSubprocessEnv:
    """Every subprocess must get env= with no secrets unless explicitly needed."""

    @pytest.mark.asyncio
    async def test_install_git_credentials_does_not_touch_environ(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_install_git_credentials must not modify os.environ."""
        calls: list[dict[str, Any]] = []

        async def fake_exec(*args: Any, **kwargs: Any) -> AsyncMock:
            calls.append({"args": list(args), "env": kwargs.get("env")})
            return _make_fake_process()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        snapshot_before = dict(os.environ)
        await _install_git_credentials(_FAKE_TOKEN, timeout=5)
        snapshot_after = dict(os.environ)

        assert snapshot_before == snapshot_after, (
            "_install_git_credentials must not modify os.environ"
        )
        assert len(calls) >= 1
        config_call = next(
            (c for c in calls if "git" in c["args"] and "config" in c["args"]),
            None,
        )
        assert config_call is not None, "Expected a git config call"
        assert config_call["env"] is not None, "git config call must have env= set"
        assert "GIT_TOKEN" not in config_call["env"], (
            "git config credential.helper call must not carry GIT_TOKEN"
        )

    @pytest.mark.asyncio
    async def test_push_env_carries_tokens(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_push must pass GIT_TOKEN and GH_TOKEN in env."""
        monkeypatch.setenv("AGENT_INTERNAL_SECRET", "must-not-appear")
        repo_env.set_git_token(_FAKE_TOKEN)
        calls: list[dict[str, Any]] = []

        async def fake_exec(*args: Any, **kwargs: Any) -> AsyncMock:
            calls.append({"args": list(args), "env": kwargs.get("env")})
            return _make_fake_process()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        await _push("my-branch", timeout=5)

        assert len(calls) >= 1
        push_call = next(
            (c for c in calls if "git" in c["args"] and "push" in c["args"]),
            None,
        )
        assert push_call is not None, "Expected a git push call"
        env = push_call["env"]
        assert env is not None
        assert env.get("GIT_TOKEN") == _FAKE_TOKEN
        assert env.get("GH_TOKEN") == _FAKE_TOKEN
        assert "AGENT_INTERNAL_SECRET" not in env

    @pytest.mark.asyncio
    async def test_has_changes_env_has_no_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """git status (has_changes) must not carry GIT_TOKEN or GH_TOKEN."""
        monkeypatch.setenv("AGENT_INTERNAL_SECRET", "must-not-appear")
        repo_env.set_git_token(_FAKE_TOKEN)
        calls: list[dict[str, Any]] = []

        async def fake_exec(*args: Any, **kwargs: Any) -> AsyncMock:
            calls.append({"args": list(args), "env": kwargs.get("env")})
            return _make_fake_process()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        await _has_changes(timeout=5)

        status_call = next(
            (c for c in calls if "git" in c["args"] and "status" in c["args"]),
            None,
        )
        assert status_call is not None, "Expected a git status call"
        env = status_call["env"]
        assert env is not None
        assert "GIT_TOKEN" not in env
        assert "GH_TOKEN" not in env
        assert "AGENT_INTERNAL_SECRET" not in env

    @pytest.mark.asyncio
    async def test_commits_ahead_fetch_has_token_revlist_does_not(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_commits_ahead: fetch call has GIT_TOKEN; rev-list call does not."""
        monkeypatch.setenv("AGENT_INTERNAL_SECRET", "must-not-appear")
        repo_env.set_git_token(_FAKE_TOKEN)
        calls: list[dict[str, Any]] = []

        async def fake_exec(*args: Any, **kwargs: Any) -> AsyncMock:
            calls.append({"args": list(args), "env": kwargs.get("env")})
            proc = _make_fake_process()
            if "rev-list" in args:
                proc.communicate = AsyncMock(return_value=(b"3\n", b""))
            return proc

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        count = await _commits_ahead("main", timeout=5)
        assert count == 3

        fetch_call = next(
            (c for c in calls if "git" in c["args"] and "fetch" in c["args"]),
            None,
        )
        revlist_call = next(
            (c for c in calls if "git" in c["args"] and "rev-list" in c["args"]),
            None,
        )
        assert fetch_call is not None
        assert revlist_call is not None
        assert fetch_call["env"] is not None
        assert fetch_call["env"].get("GIT_TOKEN") == _FAKE_TOKEN
        assert revlist_call["env"] is not None
        assert "GIT_TOKEN" not in revlist_call["env"]
        for call in calls:
            assert call["env"] is not None
            assert "AGENT_INTERNAL_SECRET" not in call["env"]

    @pytest.mark.asyncio
    async def test_run_no_git_env_has_no_secrets(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-git _run calls also use a clean env with no secret vars."""
        monkeypatch.setenv("AGENT_INTERNAL_SECRET", "must-not-appear")
        calls: list[dict[str, Any]] = []

        async def fake_exec(*args: Any, **kwargs: Any) -> AsyncMock:
            calls.append({"args": list(args), "env": kwargs.get("env")})
            return _make_fake_process()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        await _run(["echo", "hello"], "/tmp", 5)

        assert len(calls) == 1
        env = calls[0]["env"]
        assert env is not None
        for key in _SECRET_KEYS:
            assert key not in env
