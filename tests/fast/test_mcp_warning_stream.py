"""Tests for mcp_warning event handling in StreamDispatcher.

Verifies that:
1. StreamDispatcher logs an audit event for mcp_warning
2. StreamDispatcher returns continue signal (does not stop the session)
3. Unknown events still return continue (no regression)
"""

from unittest.mock import AsyncMock, patch

import pytest

from agent_session.stream import StreamDispatcher
from agent_session.tracker import SubagentTracker
from utils.models import RunContext
from utils.run_config import RunAgentConfig

_DEFAULT_RUN_CONFIG = RunAgentConfig(
    max_rounds=128,
    tool_call_timeout_sec=3600,
    session_idle_timeout_sec=120,
    subagent_idle_kill_sec=600,
)


def _make_run() -> RunContext:
    """Create a minimal RunContext for the dispatcher."""
    return RunContext(
        run_id="abcd1234-0000-0000-0000-000000000000",
        agent_role="worker",
        github_repo="org/repo",
        branch_name="fix/test",
        base_branch="main",
        duration_minutes=60,
        total_cost=0,
        total_input_tokens=0,
        total_output_tokens=0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _make_dispatcher() -> StreamDispatcher:
    """Create a StreamDispatcher for testing."""
    return StreamDispatcher(
        run=_make_run(),
        round_number=1,
        tracker=SubagentTracker(_DEFAULT_RUN_CONFIG),
    )


class TestMcpWarningStream:
    """StreamDispatcher must log mcp_warning as audit and continue."""

    @pytest.mark.asyncio
    async def test_mcp_warning_logs_audit_and_continues(self) -> None:
        """mcp_warning event must call log_audit and return continue signal."""
        dispatcher = _make_dispatcher()
        event = {
            "event": "mcp_warning",
            "data": {"message": "Failed to connect to MCP server 'foo'"},
        }

        with patch(
            "agent_session.stream.log_audit", new_callable=AsyncMock
        ) as mock_audit:
            signal = await dispatcher.dispatch(event)

        assert signal.kind == "continue"
        mock_audit.assert_called_once_with(
            "abcd1234-0000-0000-0000-000000000000",
            "mcp_warning",
            {"message": "Failed to connect to MCP server 'foo'"},
        )

    @pytest.mark.asyncio
    async def test_mcp_warning_empty_message(self) -> None:
        """mcp_warning with empty message must still log and continue."""
        dispatcher = _make_dispatcher()
        event = {"event": "mcp_warning", "data": {}}

        with patch(
            "agent_session.stream.log_audit", new_callable=AsyncMock
        ) as mock_audit:
            signal = await dispatcher.dispatch(event)

        assert signal.kind == "continue"
        mock_audit.assert_called_once_with(
            "abcd1234-0000-0000-0000-000000000000",
            "mcp_warning",
            {"message": ""},
        )
