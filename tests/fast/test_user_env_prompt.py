"""Tests for _user_env_block in prompts/loader.py."""

from prompts.loader import _user_env_block


class TestUserEnvBlock:
    """_user_env_block renders env var names or empty string."""

    def test_empty_keys_returns_empty(self) -> None:
        assert _user_env_block([]) == ""

    def test_single_key(self) -> None:
        result = _user_env_block(["MY_API_KEY"])
        assert "`MY_API_KEY`" in result
        assert "User-provided" in result

    def test_multiple_keys(self) -> None:
        result = _user_env_block(["FOO", "BAR", "BAZ"])
        assert "`FOO`" in result
        assert "`BAR`" in result
        assert "`BAZ`" in result

    def test_no_internal_keys_in_output(self) -> None:
        """If caller filters correctly, internal keys should never appear."""
        result = _user_env_block(["CUSTOM_TOKEN"])
        assert "GIT_TOKEN" not in result
        assert "CLAUDE_CODE_OAUTH_TOKEN" not in result
