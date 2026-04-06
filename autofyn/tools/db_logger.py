"""Tool call logging via SDK hooks.

DBLogger is instantiated per-run with a RunContext and registered as
SDK hook callbacks. All state (timing, subagent tracking) lives on the
instance.
"""

import logging
import time

from claude_agent_sdk.types import HookContext, HookInput, SyncHookJSONOutput

from utils import db
from utils.constants import (
    FINAL_TEXT_LIMIT,
    SUBAGENT_IDLE_KILL_SEC,
    SUBAGENT_TIMEOUT_SEC,
)
from utils.models import RunContext
from utils.helpers import read_transcript_final_text, safe_serialize

log = logging.getLogger("tools.db_logger")

_EMPTY: SyncHookJSONOutput = SyncHookJSONOutput()


class DBLogger:
    """Logs every tool interaction to the audit database.

    Public API (SDK hook callbacks):
        pre_tool_use, post_tool_use, subagent_start, subagent_stop, stop

    Public API (called by pulse checker):
        get_stuck_subagents()
    """

    def __init__(self, ctx: RunContext):
        self._ctx = ctx
        self._pre_tool_times: dict[str, float] = {}
        self._subagent_start_times: dict[str, float] = {}
        self._subagent_last_tool: dict[str, float] = {}
        self._subagent_types: dict[str, str] = {}  # agent_id → subagent name (builder, reviewer, etc.)

    # ── Stuck Detection ──

    def get_stuck_subagents(self) -> list[dict]:
        """Return subagents idle longer than the kill threshold."""
        now = time.time()
        return [
            {
                "agent_id": aid,
                "agent_type": self._subagent_types.get(aid, "unknown"),
                "idle_seconds": int(now - self._subagent_last_tool.get(aid, start_t)),
                "total_seconds": int(now - start_t),
            }
            for aid, start_t in self._subagent_start_times.items()
            if (now - self._subagent_last_tool.get(aid, start_t)) > SUBAGENT_IDLE_KILL_SEC
        ]

    # ── SDK Hook Callbacks ──

    async def pre_tool_use(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Called before every tool execution."""
        tool_name = hook_input.get("tool_name", "unknown")
        input_data = hook_input.get("tool_input", {})
        session_id = hook_input.get("session_id")
        agent_id = hook_input.get("agent_id")

        if agent_id:
            self._subagent_last_tool[agent_id] = time.time()

        timeout_result = await self._check_subagent_timeout(agent_id, tool_name)
        if timeout_result:
            return timeout_result

        if tool_use_id:
            self._pre_tool_times[tool_use_id] = time.time()

        role = self._resolve_role(agent_id)
        await db.log_tool_call(
            self._ctx.run_id, "pre", tool_name,
            safe_serialize(input_data), None, None,
            True, None, role,
            tool_use_id, session_id, agent_id,
        )
        return _EMPTY

    async def post_tool_use(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Called after every tool execution."""
        tool_name = hook_input.get("tool_name", "unknown")
        tool_response = hook_input.get("tool_response", None)
        session_id = hook_input.get("session_id")
        agent_id = hook_input.get("agent_id")

        duration_ms = None
        if tool_use_id and tool_use_id in self._pre_tool_times:
            duration_ms = int((time.time() - self._pre_tool_times.pop(tool_use_id)) * 1000)

        role = self._resolve_role(agent_id)
        await db.log_tool_call(
            self._ctx.run_id, "post", tool_name,
            None, safe_serialize(tool_response) if tool_response is not None else None,
            duration_ms, True, None, role,
            tool_use_id, session_id, agent_id,
        )
        return _EMPTY

    async def subagent_start(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Called when a subagent starts."""
        agent_id = hook_input.get("agent_id", "")
        agent_type = hook_input.get("agent_type", "")
        if agent_id:
            self._subagent_start_times[agent_id] = time.time()
            if agent_type:
                self._subagent_types[agent_id] = agent_type

        await db.log_audit(self._ctx.run_id, "subagent_start", {
            "agent_id": agent_id, "agent_type": agent_type, "tool_use_id": tool_use_id,
        })
        return _EMPTY

    async def subagent_stop(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Called when a subagent finishes."""
        agent_id = hook_input.get("agent_id", "")
        transcript_path = hook_input.get("agent_transcript_path", "")

        self._subagent_start_times.pop(agent_id, None)
        self._subagent_last_tool.pop(agent_id, None)
        self._subagent_types.pop(agent_id, None)

        final_text = read_transcript_final_text(transcript_path)

        await db.log_audit(self._ctx.run_id, "subagent_complete", {
            "agent_id": agent_id,
            "tool_use_id": tool_use_id,
            "final_text": final_text[:FINAL_TEXT_LIMIT] if final_text else "",
            "has_transcript": bool(transcript_path),
        })
        return _EMPTY

    async def stop(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Called when the agent stops."""
        await db.log_audit(self._ctx.run_id, "agent_stop", {
            "reason": hook_input.get("stop_reason", "unknown"),
            "hook_input": safe_serialize(hook_input),
        })
        return _EMPTY

    # ── Private ──

    def _resolve_role(self, agent_id: str | None) -> str:
        """Map agent_id to subagent name, or fall back to ctx.agent_role."""
        if agent_id and agent_id in self._subagent_types:
            return self._subagent_types[agent_id]
        return self._ctx.agent_role

    async def _check_subagent_timeout(self, agent_id: str | None, tool_name: str) -> SyncHookJSONOutput | None:
        """Block tool call if subagent exceeded absolute timeout."""
        if not agent_id or agent_id not in self._subagent_start_times:
            return None

        elapsed = time.time() - self._subagent_start_times[agent_id]
        if elapsed <= SUBAGENT_TIMEOUT_SEC:
            return None

        log.warning("Subagent %s timed out after %ds", agent_id, int(elapsed))
        await db.log_audit(self._ctx.run_id, "subagent_timeout", {
            "agent_id": agent_id,
            "elapsed_seconds": int(elapsed),
            "limit_seconds": SUBAGENT_TIMEOUT_SEC,
            "tool_name": tool_name,
        })
        return SyncHookJSONOutput(
            decision="block",
            reason=f"Subagent timed out after {int(elapsed)}s (limit: {SUBAGENT_TIMEOUT_SEC}s). You must stop now and return your results.",
        )
