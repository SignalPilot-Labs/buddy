"""Tests for AgentServer._process_sandbox_events().

Verifies that NDJSON events from pool.create() update DB columns:
  - queued events write sandbox_backend_id
  - log/status events are ignored (handled real-time by base_remote)
  - unknown event types are silently ignored
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer


def _make_server() -> AgentServer:
    """Build an AgentServer without triggering full __init__ (avoids Docker/DB)."""
    srv = AgentServer.__new__(AgentServer)
    srv._pool = MagicMock()
    return srv


class TestProcessSandboxEvents:
    """_process_sandbox_events writes correct DB columns."""

    @pytest.mark.asyncio
    async def test_queued_event_writes_backend_id(self) -> None:
        server = _make_server()

        mock_update_backend = AsyncMock()

        events = [{"event": "queued", "backend_id": "job-42"}]

        with patch("server.update_run_sandbox_backend_id", mock_update_backend):
            await server._process_sandbox_events("run-123", events)

        mock_update_backend.assert_awaited_once_with("run-123", "job-42")

    @pytest.mark.asyncio
    async def test_queued_event_without_backend_id_skips_update(self) -> None:
        """If backend_id is missing from queued event, DB write is skipped."""
        server = _make_server()

        mock_update_backend = AsyncMock()

        events = [{"event": "queued"}]

        with patch("server.update_run_sandbox_backend_id", mock_update_backend):
            await server._process_sandbox_events("run-123", events)

        mock_update_backend.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_log_event_ignored(self) -> None:
        """Log events are handled real-time by base_remote, not here."""
        server = _make_server()

        mock_update_backend = AsyncMock()

        events = [{"event": "log", "line": "Sandbox starting..."}]

        with patch("server.update_run_sandbox_backend_id", mock_update_backend):
            await server._process_sandbox_events("run-789", events)

        mock_update_backend.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_event_type_ignored(self) -> None:
        """Unknown event types should not cause errors."""
        server = _make_server()

        mock_update_backend = AsyncMock()

        events = [{"event": "unknown_type", "data": "whatever"}]

        with patch("server.update_run_sandbox_backend_id", mock_update_backend):
            await server._process_sandbox_events("run-xyz", events)

        mock_update_backend.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_events_list_is_noop(self) -> None:
        server = _make_server()

        mock_update_backend = AsyncMock()

        with patch("server.update_run_sandbox_backend_id", mock_update_backend):
            await server._process_sandbox_events("run-abc", [])

        mock_update_backend.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_events_all_processed(self) -> None:
        server = _make_server()

        mock_update_backend = AsyncMock()

        events = [
            {"event": "log", "line": "line 1"},
            {"event": "queued", "backend_id": "job-99"},
            {"event": "log", "line": "line 2"},
            {"event": "ready", "host": "node-5", "port": 8080},
        ]

        with patch("server.update_run_sandbox_backend_id", mock_update_backend):
            await server._process_sandbox_events("run-multi", events)

        mock_update_backend.assert_awaited_once_with("run-multi", "job-99")
