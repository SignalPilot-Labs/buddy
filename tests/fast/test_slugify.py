"""Tests for _slugify helper from sandbox_manager.repo_ops."""

from sandbox_manager.repo_ops import _slugify


class TestSlugify:
    """Tests for branch-safe slug generation."""

    def test_simple_text(self) -> None:
        assert _slugify("fix login button", 30) == "fix-login-button"

    def test_special_characters_replaced(self) -> None:
        assert _slugify("add @auth & logout!", 30) == "add-auth-logout"

    def test_truncates_to_max_len(self) -> None:
        result = _slugify("a very long prompt that exceeds the limit", 10)
        assert len(result) <= 10

    def test_no_trailing_dash_after_truncation(self) -> None:
        result = _slugify("hello world foo", 6)
        assert not result.endswith("-")

    def test_empty_string_returns_empty(self) -> None:
        assert _slugify("", 30) == ""

    def test_only_special_chars_returns_empty(self) -> None:
        assert _slugify("---!!!@@@", 30) == ""

    def test_collapses_multiple_dashes(self) -> None:
        assert _slugify("fix   the   bug", 30) == "fix-the-bug"

    def test_strips_leading_and_trailing_dashes(self) -> None:
        assert _slugify("  fix bug  ", 30) == "fix-bug"

    def test_uppercase_lowered(self) -> None:
        assert _slugify("Fix The BUG", 30) == "fix-the-bug"
