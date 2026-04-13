"""Tests for subagent attribution via the PreToolUse→SubagentStart FIFO queue.

Covers the bug where subagent tool events were rendering under the wrong
Agent card because the SubagentStart hook has no parent-link field in its
payload. The fix queues the parent Task tool_use_id at Agent PreToolUse
time and pairs it with the next SubagentStart. See PR #107.
"""

from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from claude_agent_sdk.types import (
    HookContext,
    PreToolUseHookInput,
    SubagentStartHookInput,
    SubagentStopHookInput,
)

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


def _make_session() -> Session:
    return Session("test-sess", dict(BASE_SESSION_OPTS))


def _hook_ctx() -> HookContext:
    return cast(HookContext, {"cwd": "/tmp", "session_id": "s", "transcript_path": ""})


class TestAgentPreToolUseEnqueue:
    """Agent PreToolUse hook must push the tool_use_id onto the pending queue."""

    @pytest.mark.asyncio
    async def test_agent_pre_enqueues_tool_use_id(self) -> None:
        session = _make_session()
        hook_input = cast(PreToolUseHookInput, {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "builder", "description": "d", "prompt": "p"},
            "agent_id": None,
            "session_id": "s",
        })
        with patch("sandbox.session.manager._log_tool_call", new_callable=AsyncMock):
            await session._hook_pre_tool(hook_input, "toolu_parent_1", _hook_ctx())
        assert list(session._pending_task_tool_use_ids) == ["toolu_parent_1"]

    @pytest.mark.asyncio
    async def test_non_agent_pre_does_not_enqueue(self) -> None:
        """Regular tools (Bash, Read, etc.) must not pollute the queue."""
        session = _make_session()
        hook_input = cast(PreToolUseHookInput, {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "agent_id": None,
            "session_id": "s",
        })
        with patch("sandbox.session.manager._log_tool_call", new_callable=AsyncMock):
            await session._hook_pre_tool(hook_input, "toolu_bash_1", _hook_ctx())
        assert list(session._pending_task_tool_use_ids) == []

    @pytest.mark.asyncio
    async def test_agent_pre_without_tool_use_id_raises(self) -> None:
        """Fail-fast: Agent PreToolUse must always have a tool_use_id."""
        session = _make_session()
        hook_input = cast(PreToolUseHookInput, {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "builder"},
            "agent_id": None,
            "session_id": "s",
        })
        with patch("sandbox.session.manager._log_tool_call", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="without tool_use_id"):
                await session._hook_pre_tool(hook_input, None, _hook_ctx())


class TestSubagentStartPopsQueue:
    """SubagentStart must pair with the head of the pending queue."""

    @pytest.mark.asyncio
    async def test_start_pops_fifo_and_writes_parent_tool_use_id(self) -> None:
        """The audit event must carry parent_tool_use_id from the queue."""
        session = _make_session()
        session._pending_task_tool_use_ids.append("toolu_parent_A")
        hook_input = cast(SubagentStartHookInput, {
            "agent_id": "aAgentA",
            "agent_type": "builder",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStart",
        })
        with patch("sandbox.session.manager._log_audit", new_callable=AsyncMock) as mock_audit:
            await session._hook_subagent_start(hook_input, "unrelated_hook_uuid", _hook_ctx())
        assert list(session._pending_task_tool_use_ids) == []
        assert session._subagent_parent_tuids == {"aAgentA": "toolu_parent_A"}
        mock_audit.assert_awaited_once()
        details = mock_audit.call_args[0][2]
        assert details["agent_id"] == "aAgentA"
        assert details["agent_type"] == "builder"
        assert details["parent_tool_use_id"] == "toolu_parent_A"

    @pytest.mark.asyncio
    async def test_parallel_starts_preserve_fifo_order(self) -> None:
        """Three parallel Agent PreToolUse events, three SubagentStart events:
        each start must pop the FIFO head, matching the Pre→Start order the
        SDK serializes empirically."""
        session = _make_session()
        session._pending_task_tool_use_ids.append("toolu_A")
        session._pending_task_tool_use_ids.append("toolu_B")
        session._pending_task_tool_use_ids.append("toolu_C")

        with patch("sandbox.session.manager._log_audit", new_callable=AsyncMock) as mock_audit:
            for agent_id, agent_type in [
                ("aA", "builder"),
                ("aB", "reviewer"),
                ("aC", "planner"),
            ]:
                hook_input = cast(SubagentStartHookInput, {
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "session_id": "s",
                    "transcript_path": "",
                    "cwd": "/tmp",
                    "hook_event_name": "SubagentStart",
                })
                await session._hook_subagent_start(hook_input, "uuid", _hook_ctx())

        assert session._subagent_parent_tuids == {
            "aA": "toolu_A",
            "aB": "toolu_B",
            "aC": "toolu_C",
        }
        audit_details = [c[0][2] for c in mock_audit.await_args_list]
        assert [d["parent_tool_use_id"] for d in audit_details] == [
            "toolu_A", "toolu_B", "toolu_C",
        ]

    @pytest.mark.asyncio
    async def test_start_with_empty_queue_raises(self) -> None:
        """Fail-fast: if the queue is empty at SubagentStart, the parent link
        has been lost (SDK contract violation). Raise so it's visible."""
        session = _make_session()
        hook_input = cast(SubagentStartHookInput, {
            "agent_id": "aX",
            "agent_type": "builder",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStart",
        })
        with patch("sandbox.session.manager._log_audit", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="no pending Agent"):
                await session._hook_subagent_start(hook_input, "uuid", _hook_ctx())

    @pytest.mark.asyncio
    async def test_start_missing_agent_id_raises(self) -> None:
        """Fail-fast on empty agent_id / agent_type."""
        session = _make_session()
        session._pending_task_tool_use_ids.append("toolu_x")
        hook_input = cast(SubagentStartHookInput, {
            "agent_id": "",
            "agent_type": "builder",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStart",
        })
        with patch("sandbox.session.manager._log_audit", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="missing agent_id"):
                await session._hook_subagent_start(hook_input, "uuid", _hook_ctx())


class TestSubagentStopWritesFinalText:
    """SubagentStop must persist parent_tool_use_id + last_assistant_message."""

    @pytest.mark.asyncio
    async def test_stop_writes_parent_tuid_and_final_text(self) -> None:
        session = _make_session()
        session._subagent_parent_tuids["aAgentA"] = "toolu_parent_A"
        session._subagent_start_times["aAgentA"] = 0.0
        session._subagent_types["aAgentA"] = "builder"

        hook_input = cast(SubagentStopHookInput, {
            "agent_id": "aAgentA",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
            "agent_transcript_path": "",
            "agent_type": "builder",
            "last_assistant_message": "done.",
        })
        with patch("sandbox.session.manager._log_audit", new_callable=AsyncMock) as mock_audit:
            await session._hook_subagent_stop(hook_input, "uuid", _hook_ctx())

        details = mock_audit.call_args[0][2]
        assert details["agent_id"] == "aAgentA"
        assert details["parent_tool_use_id"] == "toolu_parent_A"
        assert details["final_text"] == "done."
        # State must be cleaned up
        assert "aAgentA" not in session._subagent_parent_tuids
        assert "aAgentA" not in session._subagent_start_times
        assert "aAgentA" not in session._subagent_types

    @pytest.mark.asyncio
    async def test_stop_for_unknown_agent_raises(self) -> None:
        """Fail-fast: if SubagentStop fires for an agent_id that was never
        recorded at SubagentStart, the session state is corrupt."""
        session = _make_session()
        hook_input = cast(SubagentStopHookInput, {
            "agent_id": "aGhost",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
            "agent_transcript_path": "",
            "agent_type": "builder",
        })
        with patch("sandbox.session.manager._log_audit", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="no recorded parent"):
                await session._hook_subagent_stop(hook_input, "uuid", _hook_ctx())
