"""Tests for CLI secret masking helpers.

Verifies mask_secret, _redact_dict, print_detail, print_json, and
that services.py token preview paths use mask_secret rather than ad-hoc slices.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cli.constants import MASK_PREFIX_CLAUDE, MASK_PREFIX_DEFAULT, MASK_PREFIX_GIT
from cli.output import _redact_dict, mask_secret, print_detail, print_json


SENTINEL_CLAUDE = "sk-ant-oat01-SENTINEL1234567890abcdefghij"
SENTINEL_GIT = "ghp_SENTINELGITTOKEN123456"


class TestCliMasking:
    """Tests for mask_secret, _redact_dict, print_detail, print_json, and services."""

    # ── mask_secret ──────────────────────────────────────────────────────────

    def test_mask_secret_normal(self) -> None:
        """Variable-length asterisks after the prefix."""
        result = mask_secret(SENTINEL_CLAUDE, 8)
        assert result == "sk-ant-o" + "*" * (len(SENTINEL_CLAUDE) - 8)

    def test_mask_secret_short_value_returns_stars(self) -> None:
        """When value is shorter than or equal to prefix, return '****'."""
        assert mask_secret("short", 10) == "****"

    def test_mask_secret_empty_string_returns_empty(self) -> None:
        assert mask_secret("", 5) == ""

    def test_mask_secret_exact_prefix_length_returns_stars(self) -> None:
        """Value exactly equal to prefix_len triggers the fallback."""
        assert mask_secret("abc", 3) == "****"

    def test_mask_secret_one_over_prefix(self) -> None:
        """One character longer than prefix: prefix + one star."""
        assert mask_secret("abcd", 3) == "abc*"

    # ── _redact_dict ─────────────────────────────────────────────────────────

    def test_redact_dict_masks_secret_keys(self) -> None:
        data = {"api_key": SENTINEL_CLAUDE, "repo": "owner/name"}
        result = _redact_dict(data, frozenset({"api_key"}), MASK_PREFIX_DEFAULT)
        assert SENTINEL_CLAUDE not in result["api_key"]
        assert result["repo"] == "owner/name"

    def test_redact_dict_skips_none_values(self) -> None:
        data = {"api_key": None, "repo": "owner/name"}
        result = _redact_dict(data, frozenset({"api_key"}), MASK_PREFIX_DEFAULT)
        assert result["api_key"] is None

    def test_redact_dict_leaves_non_secret_keys_unchanged(self) -> None:
        data = {"repo": "owner/name", "budget": "10.00"}
        result = _redact_dict(data, frozenset({"api_key"}), MASK_PREFIX_DEFAULT)
        assert result == data

    # ── print_detail ─────────────────────────────────────────────────────────

    def test_print_detail_masks_secret_in_table_mode(self, capsys: pytest.CaptureFixture) -> None:
        """print_detail with secret_keys masks the secret and passes non-secret verbatim."""
        from cli.config import state
        state.json_mode = False
        print_detail(
            {"api_key": SENTINEL_CLAUDE, "repo": "owner/name"},
            secret_keys=frozenset({"api_key"}),
        )
        captured = capsys.readouterr()
        assert SENTINEL_CLAUDE not in captured.out
        assert "owner/name" in captured.out
        # The masked form starts with the MASK_PREFIX_DEFAULT (6 chars) prefix
        assert "sk-ant" in captured.out

    def test_print_detail_masks_secret_in_json_mode(self, capsys: pytest.CaptureFixture) -> None:
        """print_detail with secret_keys masks the secret even in JSON mode."""
        from cli.config import state
        state.json_mode = True
        print_detail(
            {"api_key": SENTINEL_CLAUDE, "repo": "owner/name"},
            secret_keys=frozenset({"api_key"}),
            prefix_len=8,
        )
        captured = capsys.readouterr()
        state.json_mode = False  # restore
        assert SENTINEL_CLAUDE not in captured.out
        assert "owner/name" in captured.out
        assert "sk-ant-o" in captured.out

    def test_print_detail_no_secret_keys_unchanged(self, capsys: pytest.CaptureFixture) -> None:
        """print_detail without secret_keys passes data through unchanged (back-compat)."""
        from cli.config import state
        state.json_mode = False
        print_detail({"api_key": SENTINEL_CLAUDE})
        captured = capsys.readouterr()
        assert SENTINEL_CLAUDE in captured.out

    # ── print_json ───────────────────────────────────────────────────────────

    def test_print_json_masks_secret(self, capsys: pytest.CaptureFixture) -> None:
        """print_json with secret_keys masks the secret field."""
        from cli.config import state
        state.json_mode = True
        print_json(
            {"api_key": SENTINEL_CLAUDE, "repo": "owner/name"},
            secret_keys=frozenset({"api_key"}),
            prefix_len=8,
        )
        captured = capsys.readouterr()
        assert SENTINEL_CLAUDE not in captured.out
        assert "owner/name" in captured.out

    def test_print_json_no_secret_keys_unchanged(self, capsys: pytest.CaptureFixture) -> None:
        """print_json without secret_keys is unchanged (back-compat)."""
        print_json({"api_key": SENTINEL_CLAUDE})
        captured = capsys.readouterr()
        assert SENTINEL_CLAUDE in captured.out

    def test_print_json_list_passthrough(self, capsys: pytest.CaptureFixture) -> None:
        """print_json with a list payload and secret_keys does NOT raise and outputs the list."""
        print_json(["a", "b"], secret_keys=frozenset({"a"}))
        captured = capsys.readouterr()
        assert '"a"' in captured.out
        assert '"b"' in captured.out

    # ── services.py token previews ────────────────────────────────────────────

    def test_detect_claude_token_masks_output(self, capsys: pytest.CaptureFixture) -> None:
        """_detect_claude_token must print the masked form, not the raw sentinel."""
        from cli.commands.services import _detect_claude_token

        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = f"Your OAuth token:\n\n{SENTINEL_CLAUDE}\n\nStore it."

        with (
            patch("cli.commands.services._ask_yes_no", return_value=True),
            patch("cli.commands.services.subprocess.run", return_value=fake_result),
        ):
            _detect_claude_token()

        captured = capsys.readouterr()
        full_out = captured.out + captured.err
        assert SENTINEL_CLAUDE not in full_out
        expected_prefix = SENTINEL_CLAUDE[:MASK_PREFIX_CLAUDE]
        assert expected_prefix in full_out

    def test_detect_git_token_masks_prompt(self) -> None:
        """_detect_git_token must use mask_secret, not token[:7], in its prompt."""
        from cli.commands.services import _detect_git_token

        prompt_seen: list[str] = []

        def capture_ask(prompt: str) -> bool:
            prompt_seen.append(prompt)
            return False

        with (
            patch("cli.commands.services._run_token_cmd", return_value=SENTINEL_GIT),
            patch("cli.commands.services._ask_yes_no", side_effect=capture_ask),
            patch("cli.commands.services._ask_token", return_value=None),
        ):
            _detect_git_token()

        assert prompt_seen, "Expected _ask_yes_no to be called"
        prompt_text = prompt_seen[0]
        assert SENTINEL_GIT not in prompt_text
        expected_prefix = SENTINEL_GIT[:MASK_PREFIX_GIT]
        assert expected_prefix in prompt_text
