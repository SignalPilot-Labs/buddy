"""Regression tests for connector startup.py malformed AF_* marker JSON handling.

Bug: _parse_marker called json.loads(match.group(2)) without error handling.
If the marker payload was malformed JSON (e.g., truncated, syntax error),
json.JSONDecodeError propagated, stopping the _stream_events async generator
and leaving the startup sequence in a broken state.

Fix: Wrap json.loads() in try/except JSONDecodeError — on failure log a
warning and return a log event with the raw line so the stream continues.
"""

from __future__ import annotations

import re

from cli.connector.startup import MARKER_RE, _parse_marker

SSH_TARGET = "user@hpc"


def _match(line: str) -> re.Match[str]:
    """Run MARKER_RE against line and return the match. Raises if no match."""
    m = MARKER_RE.search(line)
    assert m is not None, f"Expected MARKER_RE to match: {line!r}"
    return m


class TestParseMarkerMalformedJSON:
    """_parse_marker must return a log event instead of raising on bad JSON."""

    def test_invalid_json_returns_log_event(self) -> None:
        """Malformed JSON payload must return event='log', not raise."""
        line = 'AF_READY {invalid json here}'
        match = _match(line)
        result = _parse_marker(match, SSH_TARGET)
        assert result["event"] == "log"

    def test_log_event_line_contains_marker_prefix(self) -> None:
        """Log event line must contain 'Malformed marker JSON' prefix."""
        # Regex requires matching braces, but payload content can be invalid JSON
        line = 'AF_QUEUED {bad: unquoted key}'
        match = _match(line)
        result = _parse_marker(match, SSH_TARGET)
        assert "Malformed marker JSON" in result["line"]

    def test_log_event_line_contains_raw_payload(self) -> None:
        """Log event line must include the first 100 chars of the raw payload."""
        raw_payload = "{bad: json, no quotes}"
        line = f"AF_READY {raw_payload}"
        match = _match(line)
        result = _parse_marker(match, SSH_TARGET)
        assert raw_payload[:100] in result["line"]

    def test_truncation_to_100_chars(self) -> None:
        """Oversized payload must be truncated to 100 characters in the log line."""
        # Use a long payload with a closing brace so MARKER_RE matches
        long_inner = "x" * 200
        long_payload = f"{{{long_inner}}}"
        line = f"AF_READY {long_payload}"
        match = _match(line)
        result = _parse_marker(match, SSH_TARGET)
        payload_in_line = result["line"].replace("Malformed marker JSON: ", "")
        assert len(payload_in_line) <= 100


class TestParseMarkerValidJSON:
    """_parse_marker must continue to work correctly for valid JSON."""

    def test_valid_ready_marker_returns_ready_event(self) -> None:
        """AF_READY with valid JSON must return event='ready'."""
        line = 'AF_READY {"host": "node01", "port": 8080, "secret": "abc"}'
        match = _match(line)
        result = _parse_marker(match, SSH_TARGET)
        assert result["event"] == "ready"
        assert result["host"] == "node01"
        assert result["port"] == 8080
        assert result["sandbox_secret"] == "abc"

    def test_valid_queued_marker_returns_queued_event(self) -> None:
        """AF_QUEUED with valid JSON must return event='queued'."""
        line = 'AF_QUEUED {"backend_id": "12345"}'
        match = _match(line)
        result = _parse_marker(match, SSH_TARGET)
        assert result["event"] == "queued"
        assert result["backend_id"] == "12345"

    def test_valid_bound_marker_returns_log_event(self) -> None:
        """AF_BOUND with valid JSON must return event='log' with port info."""
        line = 'AF_BOUND {"port": 9090}'
        match = _match(line)
        result = _parse_marker(match, SSH_TARGET)
        assert result["event"] == "log"
        assert "9090" in result["line"]
