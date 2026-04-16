"""Tests for sandbox session/utils.py HTTP audit logging.

Verifies that log_audit and log_tool_call:
- POST to the correct URLs with correct headers and JSON bodies.
- Log a warning and do not raise on HTTP failure.
- Log a warning and do not raise on network error.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "sandbox-test-secret")
os.environ.setdefault("AF_AGENT_URL", "http://autofyn-agent:8500")

from session.utils import log_audit, log_tool_call
from models import ToolContext


def _make_mock_response(status: int) -> MagicMock:
    """Build a mock aiohttp response context manager."""
    resp = AsyncMock()
    resp.status = status

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_tool_context() -> ToolContext:
    return ToolContext(
        tool_name="Bash",
        tool_use_id="toolu_1",
        agent_id="agent-1",
        session_id="sess-1",
        role="worker",
        duration_ms=42,
    )


class TestLogAuditHttp:
    """log_audit makes correct HTTP calls to the agent."""

    @pytest.mark.asyncio
    async def test_posts_to_audit_endpoint(self) -> None:
        mock_resp = _make_mock_response(200)
        mock_client = MagicMock()
        mock_client.post = MagicMock(return_value=mock_resp)

        with patch("session.utils._get_agent_client", return_value=mock_client):
            await log_audit("run-1", "tool_timeout", {"tool": "Bash"})

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://autofyn-agent:8500/internal/audit"
        assert call_args[1]["json"]["run_id"] == "run-1"
        assert call_args[1]["json"]["event_type"] == "tool_timeout"
        assert call_args[1]["json"]["details"] == {"tool": "Bash"}
        assert call_args[1]["headers"]["X-Internal-Secret"] == "sandbox-test-secret"

    @pytest.mark.asyncio
    async def test_logs_warning_on_http_error(self, caplog) -> None:
        mock_resp = _make_mock_response(500)
        mock_client = MagicMock()
        mock_client.post = MagicMock(return_value=mock_resp)

        import logging
        with patch("session.utils._get_agent_client", return_value=mock_client):
            with caplog.at_level(logging.WARNING, logger="sandbox.session_utils"):
                await log_audit("run-1", "tool_timeout", {})

        assert any("500" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_does_not_raise_on_network_error(self) -> None:
        mock_client = MagicMock()
        mock_client.post = MagicMock(side_effect=Exception("Connection refused"))

        with patch("session.utils._get_agent_client", return_value=mock_client):
            # Must not raise
            await log_audit("run-1", "tool_timeout", {})


class TestLogToolCallHttp:
    """log_tool_call makes correct HTTP calls to the agent."""

    @pytest.mark.asyncio
    async def test_posts_to_tool_call_endpoint(self) -> None:
        mock_resp = _make_mock_response(200)
        mock_client = MagicMock()
        mock_client.post = MagicMock(return_value=mock_resp)

        ctx = _make_tool_context()
        with patch("session.utils._get_agent_client", return_value=mock_client):
            await log_tool_call("run-1", "pre", ctx, {"command": "ls"}, None)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://autofyn-agent:8500/internal/tool-call"
        payload = call_args[1]["json"]
        assert payload["run_id"] == "run-1"
        assert payload["phase"] == "pre"
        assert payload["tool_name"] == "Bash"
        assert payload["input_data"] == {"command": "ls"}
        assert payload["output_data"] is None
        assert payload["duration_ms"] == 42
        assert payload["permitted"] is True
        assert payload["agent_role"] == "worker"
        assert payload["tool_use_id"] == "toolu_1"
        assert call_args[1]["headers"]["X-Internal-Secret"] == "sandbox-test-secret"

    @pytest.mark.asyncio
    async def test_logs_warning_on_http_error(self, caplog) -> None:
        mock_resp = _make_mock_response(401)
        mock_client = MagicMock()
        mock_client.post = MagicMock(return_value=mock_resp)

        import logging
        ctx = _make_tool_context()
        with patch("session.utils._get_agent_client", return_value=mock_client):
            with caplog.at_level(logging.WARNING, logger="sandbox.session_utils"):
                await log_tool_call("run-1", "pre", ctx, None, None)

        assert any("401" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_does_not_raise_on_network_error(self) -> None:
        mock_client = MagicMock()
        mock_client.post = MagicMock(side_effect=Exception("Connection refused"))

        ctx = _make_tool_context()
        with patch("session.utils._get_agent_client", return_value=mock_client):
            # Must not raise
            await log_tool_call("run-1", "post", ctx, None, {"result": "ok"})
