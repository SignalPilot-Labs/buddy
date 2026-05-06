"""Regression test: malformed SSE JSON must raise JSONDecodeError, not be masked.

Previously, `_parse_sse_event` caught `json.JSONDecodeError` and returned a
fallback `{"raw": data_str}` dict. This violated the fail-fast principle and
masked serialization bugs in the sandbox.

Fix: re-raise the JSONDecodeError after logging so the caller can surface it.
"""

import json

import pytest

from sandbox_client.handlers.session import _parse_sse_event


class TestSseJsonParseError:
    """_parse_sse_event must raise JSONDecodeError on malformed JSON data."""

    def test_valid_json_parses_correctly(self) -> None:
        """Sanity: valid SSE events still parse without error."""
        raw = 'event: message\ndata: {"type": "text_delta", "text": "hello"}'
        result = _parse_sse_event(raw)
        assert result is not None
        assert result["event"] == "message"
        assert result["data"]["type"] == "text_delta"

    def test_malformed_json_raises_json_decode_error(self) -> None:
        """Malformed SSE JSON must raise JSONDecodeError instead of returning a fallback."""
        raw = "event: message\ndata: not-valid-json"
        with pytest.raises(json.JSONDecodeError):
            _parse_sse_event(raw)

    def test_truncated_json_raises_json_decode_error(self) -> None:
        """Truncated JSON object (incomplete) must raise JSONDecodeError."""
        raw = 'event: message\ndata: {"type": "text_delta"'
        with pytest.raises(json.JSONDecodeError):
            _parse_sse_event(raw)

    def test_empty_data_returns_none(self) -> None:
        """Events with no data lines must still return None (not raise)."""
        raw = "event: ping"
        result = _parse_sse_event(raw)
        assert result is None

    def test_bare_string_data_raises_json_decode_error(self) -> None:
        """A bare string value (not JSON) in data must raise JSONDecodeError."""
        raw = "data: hello world"
        with pytest.raises(json.JSONDecodeError):
            _parse_sse_event(raw)

    def test_json_null_data_parses_correctly(self) -> None:
        """JSON null is valid JSON and must parse without error."""
        raw = "data: null"
        result = _parse_sse_event(raw)
        assert result is not None
        assert result["data"] is None
