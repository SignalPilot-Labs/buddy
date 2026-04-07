"""SDK hook handlers: pre/post tool, subagent lifecycle, and stop."""

import logging
import time
from typing import Any, Callable

from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    SyncHookJSONOutput,
)

from constants import SUBAGENT_TIMEOUT_SEC
from session.logging import log_audit, log_tool_call
from session.serialization import summarize

log = logging.getLogger("sandbox.session_manager")


class HookHandlers:
    """Stateful hook handlers for a single SDK session.

    Tracks per-tool timing and per-subagent state across hook calls.
    """

    def __init__(
        self,
        run_id: str,
        emit: Callable[[dict], None],
    ) -> None:
        self._run_id = run_id
        self._emit = emit
        self._pre_tool_times: dict[str, float] = {}
        self._subagent_start_times: dict[str, float] = {}
        self._subagent_last_tool: dict[str, float] = {}
        self._subagent_types: dict[str, str] = {}

    async def hook_pre_tool(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Log pre-tool to DB. Emit tool_use event for agent stuck tracking."""
        tool_name = hook_input.get("tool_name", "unknown")
        tool_input = hook_input.get("tool_input", {})
        agent_id = hook_input.get("agent_id")
        tid = tool_use_id or ""
        sid = hook_input.get("session_id")

        blocked = await self._check_subagent_timeout(agent_id)
        if blocked is not None:
            return blocked

        if agent_id:
            self._subagent_last_tool[agent_id] = time.time()

        self._pre_tool_times[tid] = time.time()
        role = self._subagent_types.get(agent_id, "worker") if agent_id else "worker"
        await log_tool_call(
            self._run_id, "pre", tool_name,
            summarize(tool_input), None, None, True, None, role,
            tid, sid, agent_id,
        )
        self._emit({"event": "tool_use", "data": {"agent_id": agent_id}})
        return SyncHookJSONOutput()

    async def hook_post_tool(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Log post-tool to DB with duration."""
        tool_name = hook_input.get("tool_name", "unknown")
        response = hook_input.get("tool_response")
        agent_id = hook_input.get("agent_id")
        tid = tool_use_id or ""
        sid = hook_input.get("session_id")

        duration_ms = self._pop_duration_ms(tid)
        role = self._subagent_types.get(agent_id, "worker") if agent_id else "worker"
        out = summarize(response) if response is not None else None
        await log_tool_call(
            self._run_id, "post", tool_name,
            None, out, duration_ms, True, None, role,
            tid, sid, agent_id,
        )
        return SyncHookJSONOutput()

    async def hook_subagent_start(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Track subagent, log to DB, emit event for agent stuck detection."""
        agent_id = hook_input.get("agent_id", "")
        agent_type = hook_input.get("agent_type", "")
        self._subagent_start_times[agent_id] = time.time()
        self._subagent_types[agent_id] = agent_type
        await log_audit(self._run_id, "subagent_start", {
            "agent_id": agent_id, "agent_type": agent_type,
        })
        self._emit({"event": "subagent_start", "data": {
            "agent_id": agent_id, "agent_type": agent_type,
        }})
        return SyncHookJSONOutput()

    async def hook_subagent_stop(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Clean up tracking, log to DB, emit event."""
        agent_id = hook_input.get("agent_id", "")
        self._subagent_start_times.pop(agent_id, None)
        self._subagent_last_tool.pop(agent_id, None)
        self._subagent_types.pop(agent_id, None)
        await log_audit(self._run_id, "subagent_complete", {"agent_id": agent_id})
        self._emit({"event": "subagent_stop", "data": {"agent_id": agent_id}})
        return SyncHookJSONOutput()

    async def hook_stop(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Log agent stop to DB."""
        await log_audit(self._run_id, "agent_stop", {
            "reason": hook_input.get("stop_reason", "unknown"),
        })
        return SyncHookJSONOutput()

    # ── Private helpers ──

    async def _check_subagent_timeout(
        self, agent_id: Any
    ) -> SyncHookJSONOutput | None:
        """Return a blocking hook output if the subagent has timed out."""
        if not agent_id:
            return None
        if agent_id not in self._subagent_start_times:
            return None
        elapsed = time.time() - self._subagent_start_times[agent_id]
        if elapsed <= SUBAGENT_TIMEOUT_SEC:
            return None
        await log_audit(self._run_id, "subagent_timeout", {
            "agent_id": agent_id, "elapsed_seconds": int(elapsed),
        })
        return SyncHookJSONOutput(
            decision="block",
            reason=f"Subagent timed out after {int(elapsed)}s",
        )

    def _pop_duration_ms(self, tid: str) -> int | None:
        """Pop and compute duration in ms from pre-tool timestamp."""
        if tid not in self._pre_tool_times:
            return None
        return int((time.time() - self._pre_tool_times.pop(tid)) * 1000)
