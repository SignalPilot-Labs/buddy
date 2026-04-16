"""Tests for autofyn/utils/log_scrub.py — credential redaction."""

from utils.log_scrub import scrub_line, scrub_lines

# Real OAuth token fixture from test_extract_token.py
REAL_OAUTH_TOKEN = (
    "sk-ant-oat01-56BWrPjAPghnDjT09P7JOmcdzJLnpi4q6N_VyvqVVHxO0F3i"
    "Pf9gqRhcuSdYbZEl3_I6zUG3vGo0wfoyXtuKWA-HvZxpQAA"
)


class TestLogScrub:
    """scrub_line and scrub_lines redact credentials without false positives."""

    def test_real_oauth_token_redacted(self) -> None:
        line = f"token received: {REAL_OAUTH_TOKEN}"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "sk-ant-" not in result

    def test_generic_claude_api_key_redacted(self) -> None:
        line = "key=sk-ant-abcdefghijklmnop0123456789"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "sk-ant-" not in result

    def test_github_pat_ghp_redacted(self) -> None:
        line = "git_token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ01234"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "ghp_" not in result

    def test_github_pat_long_redacted(self) -> None:
        line = "token: github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_extra"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "github_pat_" not in result

    def test_x_api_key_header_redacted(self) -> None:
        line = "X-API-Key: supersecretvalue123456"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "supersecretvalue123456" not in result

    def test_x_internal_secret_header_redacted(self) -> None:
        line = "X-Internal-Secret: mysecrettoken9876543210"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "mysecrettoken9876543210" not in result

    def test_authorization_bearer_header_redacted(self) -> None:
        line = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        # Both Bearer keyword and the token value must be gone
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer" not in result

    def test_agent_internal_secret_env_form_redacted(self) -> None:
        line = "AGENT_INTERNAL_SECRET=supersecret"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "supersecret" not in result

    def test_api_key_query_param_redacted(self) -> None:
        line = "GET /api/stream?api_key=abcdef123456 HTTP/1.1"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "abcdef123456" not in result

    def test_dashboard_api_key_log_redacted(self) -> None:
        line = "[dashboard] API key: AAAAAAAABBBBBBBBCCCCCCCC"
        result = scrub_line(line)
        assert "[REDACTED]" in result
        assert "AAAAAAAABBBBBBBBCCCCCCCC" not in result

    def test_negative_no_false_positive_on_api_key_mention(self) -> None:
        """'the API key is expired' must NOT be redacted (generic phrase)."""
        line = "the API key is expired"
        result = scrub_line(line)
        assert result == line

    def test_non_matching_line_unchanged(self) -> None:
        line = "Round 1 begin — no secrets here"
        result = scrub_line(line)
        assert result == line

    def test_scrub_lines_preserves_order(self) -> None:
        lines = [
            "clean line 1",
            "sk-ant-abcdefghijklmnopqrstuvwxyz0123 leaked",
            "clean line 3",
        ]
        result = scrub_lines(lines)
        assert len(result) == 3
        assert result[0] == "clean line 1"
        assert "sk-ant-" not in result[1]
        assert "[REDACTED]" in result[1]
        assert result[2] == "clean line 3"

    def test_scrub_lines_preserves_length(self) -> None:
        lines = ["a", "b", "c", "d", "e"]
        result = scrub_lines(lines)
        assert len(result) == len(lines)

    def test_scrub_lines_empty_list(self) -> None:
        assert scrub_lines([]) == []
