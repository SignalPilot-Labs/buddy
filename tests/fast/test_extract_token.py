"""Tests for _extract_token — OAuth token parsing from claude setup-token output.

The claude CLI line-wraps stdout at 80 columns when piped, splitting
the token across lines. _extract_token must reassemble the full token.
"""

from cli.commands.services import _extract_token


FULL_TOKEN = (
    "sk-ant-oat01-56BWrPjAPghnDjT09P7JOmcdzJLnpi4q6N_VyvqVVHxO0F3i"
    "Pf9gqRhcuSdYbZEl3_I6zUG3vGo0wfoyXtuKWA-HvZxpQAA"
)


class TestExtractToken:
    """Tests for _extract_token parsing."""

    def test_single_line_token(self):
        """Token on a single line (no wrapping)."""
        stdout = f"Your OAuth token:\n\n{FULL_TOKEN}\n\nStore this token securely."
        assert _extract_token(stdout) == FULL_TOKEN

    def test_wrapped_at_80_columns(self):
        """Token wrapped at exactly 80 columns (the real bug)."""
        line1 = FULL_TOKEN[:80]
        line2 = FULL_TOKEN[80:]
        stdout = f"Your OAuth token:\n\n{line1}\n{line2}\n\nStore this token securely."
        assert _extract_token(stdout) == FULL_TOKEN

    def test_wrapped_at_60_columns(self):
        """Token wrapped at a different width."""
        line1 = FULL_TOKEN[:60]
        line2 = FULL_TOKEN[60:]
        stdout = f"Your token:\n\n{line1}\n{line2}\n\nDone."
        assert _extract_token(stdout) == FULL_TOKEN

    def test_three_line_wrap(self):
        """Token split across three lines."""
        line1 = FULL_TOKEN[:40]
        line2 = FULL_TOKEN[40:80]
        line3 = FULL_TOKEN[80:]
        stdout = f"Token:\n\n{line1}\n{line2}\n{line3}\n\nStore it."
        assert _extract_token(stdout) == FULL_TOKEN

    def test_does_not_capture_surrounding_text(self):
        """Must not merge token with 'Store this token securely' etc."""
        stdout = f"Token:\n{FULL_TOKEN}\nStore this token securely."
        result = _extract_token(stdout)
        assert result == FULL_TOKEN
        assert "Store" not in (result or "")

    def test_no_token_in_output(self):
        """Returns None when no token is present."""
        stdout = "Error: authentication failed\nTry again."
        assert _extract_token(stdout) is None

    def test_empty_string(self):
        """Returns None for empty output."""
        assert _extract_token("") is None

    def test_token_with_ansi_on_same_line(self):
        """ANSI codes on the same line as token should not be included."""
        stdout = f"Token:\n\x1b[32m{FULL_TOKEN}\x1b[0m\nDone."
        result = _extract_token(stdout)
        # ANSI prefix breaks the sk-ant- startswith check, so None is acceptable
        # as long as we never return a corrupted token
        assert result is None or result == FULL_TOKEN

    def test_token_with_leading_whitespace(self):
        """Token line with leading spaces should be stripped."""
        stdout = f"Token:\n\n   {FULL_TOKEN}\n\nDone."
        assert _extract_token(stdout) == FULL_TOKEN

    def test_short_token(self):
        """Shorter token that fits on one line."""
        short = "sk-ant-oat01-abc123-def456"
        stdout = f"Token:\n{short}\n\nDone."
        assert _extract_token(stdout) == short
