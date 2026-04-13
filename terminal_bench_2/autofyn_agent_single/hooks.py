"""SDK hooks — log tool calls and subagent lifecycle to JSONL.

Mirrors the hook logic in sandbox/session/manager.py but writes to
EventLogger (JSONL) instead of PostgreSQL.
"""

import json
import time
from typing import Any

from claude_agent_sdk.types import HookContext, HookInput, HookMatcher, SyncHookJSONOutput

from terminal_bench.constants import INPUT_SUMMARY_MAX_LEN, SUBAGENT_TIMEOUT_SEC
from terminal_bench.logger import EventLogger


class SessionHooks:
    """Pre/post tool and subagent lifecycle hooks that write to JSONL."""

    def __init__(self, logger: EventLogger) -> None:
        self._logger = logger
        self._pre_tool_times: dict[str, float] = {}
        self._subagent_start_times: dict[str, float] = {}
        self._subagent_types: dict[str, str] = {}

    def build(self) -> dict[str, list[HookMatcher]]:
        """Return hook registration dict for ClaudeAgentOptions."""
        return {
            "PreToolUse": [HookMatcher(hooks=[self._hook_pre_tool])],
            "PostToolUse": [HookMatcher(hooks=[self._hook_post_tool])],
            "PostToolUseFailure": [HookMatcher(hooks=[self._hook_post_failure])],
            "SubagentStart": [HookMatcher(hooks=[self._hook_subagent_start])],
            "SubagentStop": [HookMatcher(hooks=[self._hook_subagent_stop])],
            "Stop": [HookMatcher(hooks=[self._hook_stop])],
        }

    async def _hook_pre_tool(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        tool_name: str = hook_input.get("tool_name", "unknown")
        tool_input: dict = hook_input.get("tool_input", {})
        agent_id: str | None = hook_input.get("agent_id")
        tid = tool_use_id or ""

        if agent_id and agent_id in self._subagent_start_times:
            elapsed = time.time() - self._subagent_start_times[agent_id]
            if elapsed > SUBAGENT_TIMEOUT_SEC:
                return SyncHookJSONOutput(
                    decision="block",
                    reason=f"Subagent timed out after {int(elapsed)}s",
                )

        self._pre_tool_times[tid] = time.time()
        agent_type = self._subagent_types.get(agent_id, "orchestrator") if agent_id else "orchestrator"
        self._logger.log(
            "tool_use",
            tool=tool_name,
            input=_summarize(tool_input),
            agent_id=agent_id,
            agent_type=agent_type,
        )
        return SyncHookJSONOutput()

    async def _hook_post_tool(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        tool_name: str = hook_input.get("tool_name", "unknown")
        response: Any = hook_input.get("tool_response")
        agent_id: str | None = hook_input.get("agent_id")
        tid = tool_use_id or ""

        duration_ms: int | None = None
        if tid in self._pre_tool_times:
            duration_ms = int((time.time() - self._pre_tool_times.pop(tid)) * 1000)

        self._logger.log(
            "tool_result",
            tool=tool_name,
            duration_ms=duration_ms,
            agent_id=agent_id,
            output=_summarize(response) if response is not None else None,
        )
        return SyncHookJSONOutput()

    async def _hook_post_failure(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        tool_name: str = hook_input.get("tool_name", "unknown")
        error: str = hook_input.get("error", "unknown error")
        agent_id: str | None = hook_input.get("agent_id")
        tid = tool_use_id or ""

        duration_ms: int | None = None
        if tid in self._pre_tool_times:
            duration_ms = int((time.time() - self._pre_tool_times.pop(tid)) * 1000)

        self._logger.log(
            "tool_failure",
            tool=tool_name,
            error=error,
            duration_ms=duration_ms,
            agent_id=agent_id,
        )
        return SyncHookJSONOutput()

    async def _hook_subagent_start(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        agent_id: str = hook_input.get("agent_id", "")
        agent_type: str = hook_input.get("agent_type", "")
        self._subagent_start_times[agent_id] = time.time()
        self._subagent_types[agent_id] = agent_type
        self._logger.log("subagent_start", agent_id=agent_id, agent_type=agent_type)
        return SyncHookJSONOutput()

    async def _hook_subagent_stop(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        agent_id: str = hook_input.get("agent_id", "")
        elapsed_sec: float | None = None
        if agent_id in self._subagent_start_times:
            elapsed_sec = round(time.time() - self._subagent_start_times.pop(agent_id), 1)
        self._subagent_types.pop(agent_id, None)
        self._logger.log("subagent_stop", agent_id=agent_id, elapsed_sec=elapsed_sec)
        return SyncHookJSONOutput()

    async def _hook_stop(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        stop_reason: str = hook_input.get("stop_reason", "unknown")
        self._logger.log("agent_stop", reason=stop_reason)
        return SyncHookJSONOutput()


def _summarize(data: Any) -> dict[str, Any]:
    """Truncate large values so JSONL entries stay readable."""
    if not isinstance(data, dict):
        raw = json.dumps(data, default=str)
        if len(raw) > INPUT_SUMMARY_MAX_LEN:
            raw = raw[:INPUT_SUMMARY_MAX_LEN] + "..."
        return {"_raw": raw}
    result: dict[str, Any] = {}
    for key, val in data.items():
        if isinstance(val, str) and len(val) > INPUT_SUMMARY_MAX_LEN:
            result[key] = val[:INPUT_SUMMARY_MAX_LEN] + "..."
        else:
            result[key] = val
    return result
