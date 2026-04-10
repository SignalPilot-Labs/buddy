"""Tests for _parse_sse_event from sandbox_manager.client."""


from sandbox_client.handlers.session import _parse_sse_event


class TestParseSSEEvent:
    """Tests for SSE event parsing."""

    def test_normal_event_with_type_and_json(self):
        raw = "event: status\ndata: {\"ok\": true}"
        result = _parse_sse_event(raw)
        assert result == {"event": "status", "data": {"ok": True}}

    def test_no_data_lines_returns_none(self):
        raw = "event: ping"
        result = _parse_sse_event(raw)
        assert result is None

    def test_multi_line_data(self):
        raw = "event: chunk\ndata: {\"a\":\ndata: 1}"
        result = _parse_sse_event(raw)
        assert result == {"event": "chunk", "data": {"a": 1}}

    def test_malformed_json_falls_back_to_raw(self):
        raw = "event: error\ndata: not json at all"
        result = _parse_sse_event(raw)
        assert result == {"event": "error", "data": {"raw": "not json at all"}}

    def test_missing_event_type_defaults_to_message(self):
        raw = "data: {\"x\": 42}"
        result = _parse_sse_event(raw)
        assert result == {"event": "message", "data": {"x": 42}}

    def test_id_lines_are_ignored(self):
        raw = "id: 99\nevent: update\ndata: {\"v\": 1}"
        result = _parse_sse_event(raw)
        assert result == {"event": "update", "data": {"v": 1}}

    def test_empty_input_returns_none(self):
        result = _parse_sse_event("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = _parse_sse_event("   \n  \n  ")
        assert result is None
