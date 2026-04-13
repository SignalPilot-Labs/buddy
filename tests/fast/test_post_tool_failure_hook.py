"""Tests for PostToolUseFailure hook logging errors as post events."""

import time
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from claude_agent_sdk.types import HookContext, PostToolUseFailureHookInput
from sandbox.session.session import Session


BASE_SESSION_OPTS = {
    "run_id": "run-1",
    "model": "opus",
    "effort": "high",
    "system_prompt": "test",
    "cwd": "/tmp",
    "add_dirs": [],
    "setting_sources": {},
    "max_budget_usd": 0,
    "initial_prompt": "test",
}


class TestPostToolUseFailureHook:
    """Verify _hook_post_tool_failure logs error to DB as a post event."""

    @pytest.mark.asyncio
    async def test_failure_hook_logs_error_as_post(self) -> None:
        """PostToolUseFailure should log phase=post with output_data containing error."""
        session = Session("test-sess", dict(BASE_SESSION_OPTS))

        hook_input = {
            "tool_name": "Read",
            "error": "File not found: /nonexistent.ts",
            "agent_id": None,
            "session_id": "sess-1",
            "tool_input": {"file_path": "/nonexistent.ts"},
        }

        with patch("sandbox.session.session.log_tool_call", new_callable=AsyncMock) as mock_log:
            ctx = cast(HookContext, {"cwd": "/tmp", "session_id": "sess-1", "transcript_path": ""})
            await session._hook_post_tool_failure(cast(PostToolUseFailureHookInput, hook_input), "tu-abc", ctx)

            mock_log.assert_awaited_once()
            args = mock_log.call_args[0]
            assert args[0] == "run-1"  # run_id
            assert args[1] == "post"  # phase
            assert args[2] == "Read"  # tool_name
            assert args[3] is None  # input_data (post doesn't repeat input)
            assert args[4] == {"error": "File not found: /nonexistent.ts"}  # output_data
            assert args[9] == "tu-abc"  # tool_use_id

    @pytest.mark.asyncio
    async def test_failure_hook_tracks_duration(self) -> None:
        """PostToolUseFailure should calculate duration from pre_tool_times."""
        session = Session("test-sess", dict(BASE_SESSION_OPTS))
        # Simulate pre_tool having been called
        session._pre_tool_times["tu-abc"] = time.time() - 0.1  # 100ms ago

        hook_input = {
            "tool_name": "Read",
            "error": "File not found",
            "agent_id": None,
            "session_id": "sess-1",
        }

        with patch("sandbox.session.session.log_tool_call", new_callable=AsyncMock) as mock_log:
            ctx = cast(HookContext, {"cwd": "/tmp", "session_id": "sess-1", "transcript_path": ""})
            await session._hook_post_tool_failure(cast(PostToolUseFailureHookInput, hook_input), "tu-abc", ctx)

            args = mock_log.call_args[0]
            duration_ms = args[5]
            assert duration_ms is not None
            assert duration_ms >= 90  # at least ~100ms
            assert "tu-abc" not in session._pre_tool_times  # cleaned up
