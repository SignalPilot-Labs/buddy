"""Tests for Session._check_mcp_status warning emission."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

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
sys.modules["constants"] = constants_stub

from session.session import Session  # noqa: E402


def _make_session() -> Session:
    """Create a Session with minimal options."""
    return Session(
        session_id="test-session",
        options_dict={"run_id": "test-run"},
    )


class TestCheckMcpStatusEmitsWarnings:
    """_check_mcp_status must emit mcp_warning events for failed servers."""

    @pytest.mark.asyncio
    async def test_failed_server_emits_warning(self) -> None:
        """A server with status 'failed' must produce an mcp_warning event."""
        s = _make_session()
        client = AsyncMock()
        client.get_mcp_status = AsyncMock(return_value={
            "mcpServers": [
                {"name": "bad-server", "status": "failed", "error": "ENOENT"},
            ],
        })

        await s._check_mcp_status(client)

        event = s.events.get_nowait()
        assert event["event"] == "mcp_warning"
        assert "bad-server" in event["data"]["message"]
        assert "ENOENT" in event["data"]["message"]

    @pytest.mark.asyncio
    async def test_connected_server_no_warning(self) -> None:
        """A server with status 'connected' must not produce any event."""
        s = _make_session()
        client = AsyncMock()
        client.get_mcp_status = AsyncMock(return_value={
            "mcpServers": [
                {"name": "good-server", "status": "connected"},
            ],
        })

        await s._check_mcp_status(client)

        assert s.events.empty()

    @pytest.mark.asyncio
    async def test_multiple_failures(self) -> None:
        """Multiple failed servers must each produce a separate warning."""
        s = _make_session()
        client = AsyncMock()
        client.get_mcp_status = AsyncMock(return_value={
            "mcpServers": [
                {"name": "a", "status": "failed", "error": "err-a"},
                {"name": "b", "status": "connected"},
                {"name": "c", "status": "failed", "error": "err-c"},
            ],
        })

        await s._check_mcp_status(client)

        events = []
        while not s.events.empty():
            events.append(s.events.get_nowait())
        assert len(events) == 2
        assert "a" in events[0]["data"]["message"]
        assert "c" in events[1]["data"]["message"]

    @pytest.mark.asyncio
    async def test_get_mcp_status_exception_swallowed(self) -> None:
        """If get_mcp_status raises, the exception must be swallowed."""
        s = _make_session()
        client = AsyncMock()
        client.get_mcp_status = AsyncMock(side_effect=RuntimeError("not supported"))

        await s._check_mcp_status(client)

        assert s.events.empty()

    @pytest.mark.asyncio
    async def test_empty_mcp_servers_no_warning(self) -> None:
        """No MCP servers configured must not produce any event."""
        s = _make_session()
        client = AsyncMock()
        client.get_mcp_status = AsyncMock(return_value={"mcpServers": []})

        await s._check_mcp_status(client)

        assert s.events.empty()

    @pytest.mark.asyncio
    async def test_failed_server_without_error_field(self) -> None:
        """A failed server missing the 'error' field must use default message."""
        s = _make_session()
        client = AsyncMock()
        client.get_mcp_status = AsyncMock(return_value={
            "mcpServers": [
                {"name": "no-err", "status": "failed"},
            ],
        })

        await s._check_mcp_status(client)

        event = s.events.get_nowait()
        assert "connection failed" in event["data"]["message"]
