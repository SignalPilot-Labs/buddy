"""Unit tests for SessionHooks — tool logging, subagent tracking, emit behavior."""

from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from claude_agent_sdk.types import (
    HookContext,
    PreToolUseHookInput,
    PostToolUseHookInput,
    SubagentStartHookInput,
    SubagentStopHookInput,
    StopHookInput,
)

from session.hooks import SessionHooks


def _make_hooks() -> tuple[SessionHooks, list[dict]]:
    """Create a SessionHooks with a capturing emit function."""
    emitted: list[dict] = []
    hooks = SessionHooks("run-1", emitted.append)
    return hooks, emitted


def _ctx() -> HookContext:
    return cast(HookContext, {"cwd": "/tmp", "session_id": "s", "transcript_path": ""})


class TestPreToolEmitsToolUse:
    """PreToolUse must emit tool_use SSE and log to DB."""

    @pytest.mark.asyncio
    async def test_emits_tool_use_event(self) -> None:
        hooks, emitted = _make_hooks()
        hook_input = cast(PreToolUseHookInput, {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "agent_id": "a1",
            "session_id": "s",
        })
        with patch("session.hooks.log_tool_call", new_callable=AsyncMock):
            await hooks._hook_pre_tool(hook_input, "tu-1", _ctx())

        assert len(emitted) == 1
        assert emitted[0]["event"] == "tool_use"
        assert emitted[0]["data"]["agent_id"] == "a1"

    @pytest.mark.asyncio
    async def test_records_pre_tool_time(self) -> None:
        hooks, _ = _make_hooks()
        hook_input = cast(PreToolUseHookInput, {
            "tool_name": "Read",
            "tool_input": {},
            "agent_id": None,
            "session_id": "s",
        })
        with patch("session.hooks.log_tool_call", new_callable=AsyncMock):
            await hooks._hook_pre_tool(hook_input, "tu-2", _ctx())

        assert "tu-2" in hooks._pre_tool_times


class TestPostToolEmitsToolDone:
    """PostToolUse must emit tool_done SSE."""

    @pytest.mark.asyncio
    async def test_emits_tool_done_event(self) -> None:
        hooks, emitted = _make_hooks()
        hook_input = cast(PostToolUseHookInput, {
            "tool_name": "Bash",
            "tool_response": "output",
            "agent_id": "a1",
            "session_id": "s",
        })
        with patch("session.hooks.log_tool_call", new_callable=AsyncMock):
            await hooks._hook_post_tool(hook_input, "tu-1", _ctx())

        assert len(emitted) == 1
        assert emitted[0]["event"] == "tool_done"

    @pytest.mark.asyncio
    async def test_computes_duration_from_pre_tool(self) -> None:
        hooks, _ = _make_hooks()
        import time
        hooks._pre_tool_times["tu-1"] = time.time() - 0.05

        hook_input = cast(PostToolUseHookInput, {
            "tool_name": "Bash",
            "tool_response": "ok",
            "agent_id": None,
            "session_id": "s",
        })
        with patch("session.hooks.log_tool_call", new_callable=AsyncMock) as mock:
            await hooks._hook_post_tool(hook_input, "tu-1", _ctx())

        ctx_arg = mock.call_args[0][2]
        assert ctx_arg.duration_ms is not None
        assert ctx_arg.duration_ms >= 40
        assert "tu-1" not in hooks._pre_tool_times


class TestSubagentLifecycleEvents:
    """SubagentStart/Stop must emit correct SSE events."""

    @pytest.mark.asyncio
    async def test_start_emits_subagent_start(self) -> None:
        hooks, emitted = _make_hooks()
        hooks._pending_task_tool_use_ids.append("toolu_p1")

        hook_input = cast(SubagentStartHookInput, {
            "agent_id": "a1",
            "agent_type": "builder",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStart",
        })
        with patch("session.hooks.log_audit", new_callable=AsyncMock):
            await hooks._hook_subagent_start(hook_input, "uuid", _ctx())

        assert len(emitted) == 1
        assert emitted[0]["event"] == "subagent_start"
        assert emitted[0]["data"]["agent_id"] == "a1"
        assert emitted[0]["data"]["parent_tool_use_id"] == "toolu_p1"

    @pytest.mark.asyncio
    async def test_stop_emits_subagent_stop(self) -> None:
        hooks, emitted = _make_hooks()
        hooks._subagent_parent_tuids["a1"] = "toolu_p1"
        hooks._subagent_start_times["a1"] = 0.0
        hooks._subagent_types["a1"] = "builder"

        hook_input = cast(SubagentStopHookInput, {
            "agent_id": "a1",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
            "agent_transcript_path": "",
            "agent_type": "builder",
            "last_assistant_message": "done",
        })
        with patch("session.hooks.log_audit", new_callable=AsyncMock):
            await hooks._hook_subagent_stop(hook_input, "uuid", _ctx())

        assert len(emitted) == 1
        assert emitted[0]["event"] == "subagent_stop"
        assert "a1" not in hooks._subagent_start_times

    @pytest.mark.asyncio
    async def test_stop_hook_logs_reason(self) -> None:
        hooks, _ = _make_hooks()
        hook_input = cast(StopHookInput, {"stop_reason": "user_cancelled"})
        with patch("session.hooks.log_audit", new_callable=AsyncMock) as mock:
            await hooks._hook_stop(hook_input, None, _ctx())

        mock.assert_awaited_once()
        assert mock.call_args[0][1] == "agent_stop"
        assert mock.call_args[0][2]["reason"] == "user_cancelled"
