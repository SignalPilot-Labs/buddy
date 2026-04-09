"""Tests for per-run token isolation — tokens flow via env dict, not os.environ."""

import os

from utils.constants import ENV_KEY_CLAUDE_TOKEN, ENV_KEY_GIT_TOKEN
from utils.run_helpers import merge_tokens_into_env


class TestTokenIsolation:
    """Verify that tokens are merged into body.env and never touch os.environ."""

    def test_tokens_merged_into_env_dict(self) -> None:
        result = merge_tokens_into_env(None, "tok-a", "tok-b")
        assert result is not None
        assert result[ENV_KEY_CLAUDE_TOKEN] == "tok-a"
        assert result[ENV_KEY_GIT_TOKEN] == "tok-b"

    def test_tokens_do_not_touch_os_environ(self) -> None:
        original_claude = os.environ.get(ENV_KEY_CLAUDE_TOKEN)
        original_git = os.environ.get(ENV_KEY_GIT_TOKEN)

        merge_tokens_into_env(None, "tok-a", "tok-b")

        assert os.environ.get(ENV_KEY_CLAUDE_TOKEN) == original_claude
        assert os.environ.get(ENV_KEY_GIT_TOKEN) == original_git

    def test_existing_env_preserved_with_tokens(self) -> None:
        existing = {"CUSTOM": "val"}
        result = merge_tokens_into_env(existing, "tok-a", "tok-b")
        assert result is not None
        assert result["CUSTOM"] == "val"
        assert result[ENV_KEY_CLAUDE_TOKEN] == "tok-a"
        assert result[ENV_KEY_GIT_TOKEN] == "tok-b"

    def test_no_tokens_returns_env_unchanged(self) -> None:
        env: dict[str, str] = {"CUSTOM": "val"}
        result = merge_tokens_into_env(env, None, None)
        assert result is env

    def test_no_tokens_with_none_env_returns_none(self) -> None:
        result = merge_tokens_into_env(None, None, None)
        assert result is None
