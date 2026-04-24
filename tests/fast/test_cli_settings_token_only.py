"""Regression test for CLI settings set --claude-token reporting failure after success.

Previously, when only --claude-token was provided, the token was added to the
pool successfully, but then the `if not body:` check raised typer.Exit(1) because
`body` only contains settings keys, not the token pool key. The fix returns early
with success when claude_token was handled and body is otherwise empty.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer

from cli.commands.settings import set_settings


def _make_client(post_return: dict, put_return: dict | None = None) -> MagicMock:
    """Build a mock AutoFynClient."""
    client = MagicMock()
    client.post.return_value = post_return
    if put_return is not None:
        client.put.return_value = put_return
    return client


class TestCliSettingsTokenOnly:
    """set_settings must succeed when only --claude-token is provided."""

    def test_token_only_does_not_exit_with_error(self) -> None:
        """Providing only --claude-token must not raise typer.Exit(1)."""
        client = _make_client(post_return={"ok": True, "count": 1})

        with patch("cli.commands.settings.get_client", return_value=client):
            # Must not raise typer.Exit at all, or if it does, not with code 1
            try:
                set_settings(
                    claude_token="sk-test-token",
                    git_token=None,
                    github_repo=None,
                    budget=None,
                    api_key=None,
                )
            except typer.Exit as exc:
                assert exc.exit_code != 1, (
                    "set_settings raised typer.Exit(1) after successfully adding token"
                )

    def test_token_only_calls_post_tokens(self) -> None:
        """Providing only --claude-token must POST to /api/tokens."""
        client = _make_client(post_return={"ok": True, "count": 1})

        with patch("cli.commands.settings.get_client", return_value=client):
            try:
                set_settings(
                    claude_token="sk-test-token",
                    git_token=None,
                    github_repo=None,
                    budget=None,
                    api_key=None,
                )
            except typer.Exit:
                pass

        client.post.assert_called_once_with("/api/tokens", json={"token": "sk-test-token"})

    def test_token_only_does_not_call_put_settings(self) -> None:
        """Providing only --claude-token must NOT call PUT /api/settings."""
        client = _make_client(post_return={"ok": True, "count": 1})

        with patch("cli.commands.settings.get_client", return_value=client):
            try:
                set_settings(
                    claude_token="sk-test-token",
                    git_token=None,
                    github_repo=None,
                    budget=None,
                    api_key=None,
                )
            except typer.Exit:
                pass

        client.put.assert_not_called()

    def test_no_args_exits_with_error(self) -> None:
        """Providing no options must still exit with code 1."""
        client = _make_client(post_return={})

        with patch("cli.commands.settings.get_client", return_value=client):
            with pytest.raises(typer.Exit) as exc_info:
                set_settings(
                    claude_token=None,
                    git_token=None,
                    github_repo=None,
                    budget=None,
                    api_key=None,
                )
        assert exc_info.value.exit_code == 1

    def test_token_plus_other_flag_calls_both(self) -> None:
        """When --claude-token and --git-token are both set, both endpoints are called."""
        client = _make_client(
            post_return={"ok": True, "count": 1},
            put_return={"updated": ["git_token"]},
        )

        with patch("cli.commands.settings.get_client", return_value=client):
            set_settings(
                claude_token="sk-test-token",
                git_token="ghp_abc",
                github_repo=None,
                budget=None,
                api_key=None,
            )

        client.post.assert_called_once_with("/api/tokens", json={"token": "sk-test-token"})
        client.put.assert_called_once_with("/api/settings", json={"git_token": "ghp_abc"})
