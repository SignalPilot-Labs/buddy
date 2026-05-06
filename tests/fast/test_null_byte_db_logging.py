"""Regression test: null bytes in tool call output must not crash DB insert.

Bug: security-reviewer ran shlex.quote with \\x00 input. The output
contained a null byte which PostgreSQL rejects in JSONB columns. The
unhandled DB error crashed the round, which cascaded into an aclose()
RuntimeError on the SSE generator.

Fix: _strip_null_bytes sanitizes input/output before insert, and
log_tool_call_idempotent swallows DB errors instead of propagating.
"""

import json

from utils.db_logging import _strip_null_bytes


class TestStripNullBytes:
    """_strip_null_bytes removes \\x00 from dicts before PostgreSQL insert."""

    def test_returns_none_for_none(self) -> None:
        assert _strip_null_bytes(None) is None

    def test_passes_clean_dict_through(self) -> None:
        data = {"stdout": "hello world", "exit_code": 0}
        assert _strip_null_bytes(data) == data

    def test_strips_literal_null_byte(self) -> None:
        data = {"stdout": "before\x00after"}
        result = _strip_null_bytes(data)
        assert result is not None
        assert "\x00" not in result["stdout"]
        assert result["stdout"] == "beforeafter"

    def test_strips_unicode_null_escape(self) -> None:
        data = {"stdout": "test\\u0000null"}
        result = _strip_null_bytes(data)
        assert result is not None
        assert "\\u0000" not in json.dumps(result)

    def test_strips_null_in_nested_dict(self) -> None:
        data = {"result": {"path": "/tmp/test\x00file.sif"}}
        result = _strip_null_bytes(data)
        assert result is not None
        assert "\x00" not in result["result"]["path"]

    def test_strips_null_in_list_values(self) -> None:
        data = {"args": ["echo", "hello\x00world"]}
        result = _strip_null_bytes(data)
        assert result is not None
        assert "\x00" not in result["args"][1]

    def test_preserves_other_special_chars(self) -> None:
        data = {"stdout": "line1\nline2\ttab"}
        result = _strip_null_bytes(data)
        assert result == data
