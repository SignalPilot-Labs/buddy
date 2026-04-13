"""Integration tests for Session → SessionHooks → SessionGate wiring.

Verifies that the refactored Session correctly delegates to hooks and
gate, and that the event queue receives the right SSE events through
the full call chain.
"""

from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from claude_agent_sdk.types import (
    HookContext,
    PreToolUseHookInput,
    PostToolUseHookInput,
    SubagentStartHookInput,
    SubagentStopHookInput,
)

from session.session import Session


BASE_OPTS = {
    "run_id": "run-integration",
    "model": "opus",
    "effort": "high",
    "system_prompt": "test",
    "cwd": "/tmp",
    "add_dirs": [],
    "setting_sources": {},
    "max_budget_usd": 0,
    "initial_prompt": "test",
}


def _ctx() -> HookContext:
    return cast(HookContext, {"cwd": "/tmp", "session_id": "s", "transcript_path": ""})


def _drain_queue(session: Session) -> list[dict]:
    """Drain all events from the session queue."""
    events = []
    while not session.events.empty():
        events.append(session.events.get_nowait())
    return events


class TestSessionDelegation:
    """Session must wire hooks and gate through _emit correctly."""

    @pytest.mark.asyncio
    async def test_hook_events_reach_session_queue(self) -> None:
        """Tool hooks called through session._hooks must emit to session.events."""
        session = Session("sess-1", dict(BASE_OPTS))
        hooks = session._hooks

        hook_input = cast(PreToolUseHookInput, {
            "tool_name": "Bash",
            "tool_input": {"command": "echo"},
            "agent_id": None,
            "session_id": "s",
        })
        with patch("session.hooks.log_tool_call", new_callable=AsyncMock):
            await hooks._hook_pre_tool(hook_input, "tu-1", _ctx())

        events = _drain_queue(session)
        assert any(e["event"] == "tool_use" for e in events)

    @pytest.mark.asyncio
    async def test_post_tool_done_reaches_queue(self) -> None:
        """PostToolUse tool_done event must reach the session queue."""
        session = Session("sess-1", dict(BASE_OPTS))
        hooks = session._hooks

        hook_input = cast(PostToolUseHookInput, {
            "tool_name": "Bash",
            "tool_response": "ok",
            "agent_id": "a1",
            "session_id": "s",
        })
        with patch("session.hooks.log_tool_call", new_callable=AsyncMock):
            await hooks._hook_post_tool(hook_input, "tu-1", _ctx())

        events = _drain_queue(session)
        assert any(e["event"] == "tool_done" for e in events)

    @pytest.mark.asyncio
    async def test_mark_ended_wired_to_session(self) -> None:
        """SessionGate.mark_ended must set Session._ended."""
        session = Session("sess-1", dict(BASE_OPTS))
        assert not session._ended
        session._gate._mark_ended()
        assert session._ended

    @pytest.mark.asyncio
    async def test_unlock_wired_to_gate(self) -> None:
        """Session.unlocked must be visible to SessionGate."""
        session = Session("sess-1", dict(BASE_OPTS))
        assert not session._gate._is_unlocked()
        session.unlocked = True
        assert session._gate._is_unlocked()


class TestFullToolLifecycle:
    """End-to-end: pre_tool → post_tool produces tool_use + tool_done in queue."""

    @pytest.mark.asyncio
    async def test_pre_then_post_produces_both_events(self) -> None:
        session = Session("sess-1", dict(BASE_OPTS))
        hooks = session._hooks

        pre_input = cast(PreToolUseHookInput, {
            "tool_name": "Bash",
            "tool_input": {"command": "sleep 1"},
            "agent_id": "a1",
            "session_id": "s",
        })
        post_input = cast(PostToolUseHookInput, {
            "tool_name": "Bash",
            "tool_response": "done",
            "agent_id": "a1",
            "session_id": "s",
        })

        with patch("session.hooks.log_tool_call", new_callable=AsyncMock):
            await hooks._hook_pre_tool(pre_input, "tu-1", _ctx())
            await hooks._hook_post_tool(post_input, "tu-1", _ctx())

        events = _drain_queue(session)
        event_types = [e["event"] for e in events]
        assert event_types == ["tool_use", "tool_done"]


class TestFullSubagentLifecycle:
    """End-to-end: pre_tool(Agent) → subagent_start → subagent_stop."""

    @pytest.mark.asyncio
    async def test_agent_spawn_to_stop(self) -> None:
        session = Session("sess-1", dict(BASE_OPTS))
        hooks = session._hooks

        # 1. Agent PreToolUse
        pre_input = cast(PreToolUseHookInput, {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "builder", "prompt": "p"},
            "agent_id": None,
            "session_id": "s",
        })
        with patch("session.hooks.log_tool_call", new_callable=AsyncMock):
            await hooks._hook_pre_tool(pre_input, "toolu_parent", _ctx())

        # 2. SubagentStart
        start_input = cast(SubagentStartHookInput, {
            "agent_id": "aBuilder",
            "agent_type": "builder",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStart",
        })
        with patch("session.hooks.log_audit", new_callable=AsyncMock):
            await hooks._hook_subagent_start(start_input, "uuid", _ctx())

        # 3. SubagentStop
        stop_input = cast(SubagentStopHookInput, {
            "agent_id": "aBuilder",
            "session_id": "s",
            "transcript_path": "",
            "cwd": "/tmp",
            "hook_event_name": "SubagentStop",
            "stop_hook_active": False,
            "agent_transcript_path": "",
            "agent_type": "builder",
            "last_assistant_message": "all done",
        })
        with patch("session.hooks.log_audit", new_callable=AsyncMock):
            await hooks._hook_subagent_stop(stop_input, "uuid", _ctx())

        events = _drain_queue(session)
        event_types = [e["event"] for e in events]
        assert event_types == ["tool_use", "subagent_start", "subagent_stop"]
        # State should be fully cleaned up
        assert len(hooks._subagent_parent_tuids) == 0
        assert len(hooks._subagent_start_times) == 0
        assert len(hooks._subagent_types) == 0
