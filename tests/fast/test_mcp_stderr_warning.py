"""Tests for Session._stderr_callback MCP warning emission."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Stub heavy dependencies before importing session module.
for mod in (
    "claude_agent_sdk",
    "claude_agent_sdk.types",
    "config.loader",
    "session.gate",
    "session.hooks",
    "session.security",
    "session.utils",
):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Stub constants that session.py imports.
constants_stub = MagicMock()
constants_stub.SESSION_EVENT_QUEUE_SIZE = 100
constants_stub.TERMINAL_EVENTS = frozenset({"session_end", "session_error"})
constants_stub.MAX_MCP_WARNINGS = 5
sys.modules["constants"] = constants_stub

from session.session import Session  # noqa: E402


def _make_session() -> Session:
    """Create a Session with minimal options."""
    return Session(
        session_id="test-session",
        options_dict={"run_id": "test-run"},
    )


class TestStderrCallbackFiltering:
    """_stderr_callback must only emit events for MCP-related lines."""

    def test_mcp_line_emits_event(self) -> None:
        """Stderr line containing 'mcp' must produce an mcp_warning event."""
        s = _make_session()
        s._stderr_callback("Failed to connect to MCP server 'foo'")

        event = s.events.get_nowait()
        assert event["event"] == "mcp_warning"
        assert "foo" in event["data"]["message"]

    def test_non_mcp_line_ignored(self) -> None:
        """Stderr line without 'mcp' must not produce any event."""
        s = _make_session()
        s._stderr_callback("Some unrelated log line")

        assert s.events.empty()

    def test_case_insensitive(self) -> None:
        """MCP detection must be case-insensitive."""
        s = _make_session()
        s._stderr_callback("MCP connection timeout")

        event = s.events.get_nowait()
        assert event["event"] == "mcp_warning"


class TestStderrCallbackRateLimit:
    """_stderr_callback must cap emitted warnings at MAX_MCP_WARNINGS."""

    def test_stops_emitting_after_max(self) -> None:
        """Only MAX_MCP_WARNINGS events must be emitted; extras are dropped."""
        s = _make_session()
        max_warnings = constants_stub.MAX_MCP_WARNINGS

        for i in range(max_warnings + 5):
            s._stderr_callback(f"MCP error #{i}")

        count = 0
        while not s.events.empty():
            s.events.get_nowait()
            count += 1

        assert count == max_warnings

    def test_non_mcp_lines_dont_count(self) -> None:
        """Non-MCP lines must not consume the rate limit budget."""
        s = _make_session()
        max_warnings = constants_stub.MAX_MCP_WARNINGS

        for _ in range(20):
            s._stderr_callback("unrelated noise")

        for i in range(max_warnings):
            s._stderr_callback(f"MCP error #{i}")

        count = 0
        while not s.events.empty():
            s.events.get_nowait()
            count += 1

        assert count == max_warnings
