"""Session — a single Claude SDK session running in the sandbox.

Owns the SDK client lifecycle, event queue, hooks (tool logging, subagent
tracking), permission gating, and MCP session gate tools (end_round,
end_session).
"""

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk import tool, create_sdk_mcp_server
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    SyncHookJSONOutput,
    ToolPermissionContext,
)

from constants import (
    EARLY_EXIT_THRESHOLD_MIN,
    SECONDS_PER_MINUTE,
    SESSION_EVENT_QUEUE_SIZE,
    SUBAGENT_TIMEOUT_SEC,
    TASK_TOOL_NAME,
)
from db.constants import resolve_sdk_model
from session.security import SecurityGate
from session.utils import (
    log_audit,
    log_tool_call,
    parse_agents,
    serialize_message,
    summarize,
)

log = logging.getLogger("sandbox.session")


class Session:
    """A single Claude SDK session running in the sandbox."""

    def __init__(self, session_id: str, options_dict: dict) -> None:
        self.session_id = session_id
        self.options_dict = options_dict
        self.events: asyncio.Queue = asyncio.Queue(maxsize=SESSION_EVENT_QUEUE_SIZE)
        self.client: ClaudeSDKClient | None = None
        self.task: asyncio.Task | None = None
        self._ended = False
        self.unlocked = False
        # Hook state
        self._pre_tool_times: dict[str, float] = {}
        self._subagent_start_times: dict[str, float] = {}
        self._subagent_last_tool: dict[str, float] = {}
        self._subagent_types: dict[str, str] = {}
        # Parent Task tool_use_id tracking for subagent attribution. The
        # SubagentStart hook payload has no way to identify which Agent/Task
        # call spawned it, but the SDK fires each Agent PreToolUse
        # immediately before its corresponding SubagentStart (verified for
        # parallel Task calls). We queue Agent pre-tool tool_use_ids here
        # and pop them in FIFO order at SubagentStart. The resulting
        # agent_id -> parent_tool_use_id map lets SubagentStop emit the
        # same link so the dashboard can attribute final text as well.
        self._pending_task_tool_use_ids: deque[str] = deque()
        self._subagent_parent_tuids: dict[str, str] = {}

    @property
    def _run_id(self) -> str:
        """Run ID from options."""
        return self.options_dict.get("run_id", "")

    async def run(self) -> None:
        """Run the SDK session, pushing events to the queue.

        Uses receive_messages() (persistent iterator) instead of
        receive_response() (single-turn) so follow-up queries sent via
        send_message() are streamed back through the same loop.
        """
        try:
            options = self._build_options()
            async with ClaudeSDKClient(options=options) as client:
                self.client = client
                await client.query(self.options_dict["initial_prompt"])
                async for message in client.receive_messages():
                    event = serialize_message(message)
                    if event:
                        self._emit(event)
                    if self._ended:
                        break
            self._emit({"event": "session_end", "data": {}})
        except asyncio.CancelledError:
            self._emit({"event": "session_end", "data": {"reason": "cancelled"}})
        except Exception as e:
            log.error("Session %s error: %s", self.session_id, e, exc_info=True)
            self._emit({"event": "session_error", "data": {"error": str(e)}})

    def _emit(self, event: dict) -> None:
        """Put event on queue. Drops oldest if full."""
        try:
            self.events.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("Session %s queue full, dropping oldest", self.session_id)
            try:
                self.events.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.events.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def _build_options(self) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions from the options dict."""
        opts = self.options_dict
        gate = SecurityGate(opts["github_repo"], opts["branch_name"])
        mcp = dict(opts.get("mcp_servers") or {})
        gate_cfg = opts.get("session_gate")
        if gate_cfg:
            mcp["session_gate"] = self._build_session_gate_mcp(gate_cfg)

        agents_raw = opts.get("agents")
        agents = parse_agents(agents_raw) if agents_raw else None

        return ClaudeAgentOptions(
            model=resolve_sdk_model(opts["model"]),
            fallback_model=(
                resolve_sdk_model(opts["fallback_model"])
                if opts.get("fallback_model")
                else None
            ),
            effort=opts["effort"],
            system_prompt=opts["system_prompt"],
            permission_mode="bypassPermissions",
            can_use_tool=self._permission_callback(gate),
            cwd=opts["cwd"],
            add_dirs=opts["add_dirs"],
            setting_sources=opts["setting_sources"],
            max_budget_usd=opts["max_budget_usd"],
            include_partial_messages=True,
            resume=opts.get("resume"),
            mcp_servers=mcp,
            agents=agents,
            hooks=self._build_hooks(),
        )

    # ── Permission callback ──

    def _permission_callback(self, gate: SecurityGate) -> Callable:
        """Create permission callback bound to a SecurityGate."""

        async def _check(
            tool_name: str,
            input_data: dict,
            context: ToolPermissionContext,
        ) -> PermissionResultAllow | PermissionResultDeny:
            deny = gate.check_permission(tool_name, input_data)
            if deny:
                await log_audit(
                    self._run_id,
                    "permission_denied",
                    {
                        "tool_name": tool_name,
                        "reason": deny,
                    },
                )
                return PermissionResultDeny(message=deny)
            return PermissionResultAllow(updated_input=input_data)

        return _check

    # ── SDK hooks (log to DB, emit minimal SSE for agent tracking) ──

    def _build_hooks(self) -> dict:
        """Build SDK hook registrations."""
        return {
            "PreToolUse": [HookMatcher(hooks=[self._hook_pre_tool])],
            "PostToolUse": [HookMatcher(hooks=[self._hook_post_tool])],
            "PostToolUseFailure": [HookMatcher(hooks=[self._hook_post_tool_failure])],
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
        """Log pre-tool to DB. Emit tool_use event for agent stuck tracking."""
        tool_name = hook_input.get("tool_name", "unknown")
        tool_input = hook_input.get("tool_input", {})
        agent_id = hook_input.get("agent_id")
        tid = tool_use_id or ""
        sid = hook_input.get("session_id")

        if agent_id:
            self._subagent_last_tool[agent_id] = time.time()
            # Check timeout
            if agent_id in self._subagent_start_times:
                elapsed = time.time() - self._subagent_start_times[agent_id]
                if elapsed > SUBAGENT_TIMEOUT_SEC:
                    await log_audit(
                        self._run_id,
                        "subagent_timeout",
                        {
                            "agent_id": agent_id,
                            "elapsed_seconds": int(elapsed),
                        },
                    )
                    return SyncHookJSONOutput(
                        decision="block",
                        reason=f"Subagent timed out after {int(elapsed)}s",
                    )

        self._pre_tool_times[tid] = time.time()
        role = self._subagent_types.get(agent_id, "worker") if agent_id else "worker"
        await log_tool_call(
            self._run_id,
            "pre",
            tool_name,
            summarize(tool_input),
            None,
            None,
            True,
            None,
            role,
            tid,
            sid,
            agent_id,
        )
        # Queue parent Task tool_use_id for the SubagentStart that will
        # fire next. The SDK has no direct payload link between Agent
        # PreToolUse and SubagentStart, but it serializes them 1:1 even
        # for parallel Task calls (verified empirically).
        if tool_name == TASK_TOOL_NAME:
            if tool_use_id is None:
                raise RuntimeError(
                    f"PreToolUse for {TASK_TOOL_NAME} fired without tool_use_id"
                )
            self._pending_task_tool_use_ids.append(tool_use_id)
        self._emit({"event": "tool_use", "data": {"agent_id": agent_id}})
        return SyncHookJSONOutput()

    def _resolve_post_tool_context(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
    ) -> tuple[str, str, str, str | None, int | None]:
        """Extract common fields and compute duration for post-tool hooks."""
        tool_name = hook_input.get("tool_name", "unknown")
        agent_id = hook_input.get("agent_id")
        tid = tool_use_id or ""
        sid = hook_input.get("session_id")
        duration_ms = None
        if tid in self._pre_tool_times:
            duration_ms = int((time.time() - self._pre_tool_times.pop(tid)) * 1000)
        role = self._subagent_types.get(agent_id, "worker") if agent_id else "worker"
        return tool_name, tid, role, sid, duration_ms

    async def _hook_post_tool(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Log post-tool to DB with duration."""
        tool_name, tid, role, sid, duration_ms = self._resolve_post_tool_context(
            hook_input, tool_use_id
        )
        agent_id = hook_input.get("agent_id")
        response = hook_input.get("tool_response")
        out = summarize(response) if response is not None else None
        await log_tool_call(
            self._run_id,
            "post",
            tool_name,
            None,
            out,
            duration_ms,
            True,
            None,
            role,
            tid,
            sid,
            agent_id,
        )
        return SyncHookJSONOutput()

    async def _hook_post_tool_failure(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Log failed tool to DB with error. Fires instead of PostToolUse on failure."""
        tool_name, tid, role, sid, duration_ms = self._resolve_post_tool_context(
            hook_input, tool_use_id
        )
        agent_id = hook_input.get("agent_id")
        error = hook_input.get("error", "unknown error")
        await log_tool_call(
            self._run_id,
            "post",
            tool_name,
            None,
            {"error": error},
            duration_ms,
            True,
            None,
            role,
            tid,
            sid,
            agent_id,
        )
        return SyncHookJSONOutput()

    async def _hook_subagent_start(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Track subagent, log to DB, emit event for agent stuck detection.

        The SubagentStart hook payload has no parent Task tool_use_id field,
        and the SDK callback's tool_use_id parameter is an unrelated
        per-hook UUID. The parent link is recovered from the FIFO queue
        populated in _hook_pre_tool when it saw the Agent PreToolUse that
        spawned this subagent. Persisting parent_tool_use_id here lets
        the dashboard deterministically attribute subagent tools to the
        correct Agent card (see groupEvents.ts).
        """
        agent_id = hook_input.get("agent_id", "")
        agent_type = hook_input.get("agent_type", "")
        if not agent_id or not agent_type:
            raise RuntimeError(
                f"SubagentStart missing agent_id/agent_type: "
                f"agent_id={agent_id!r} agent_type={agent_type!r}"
            )
        if not self._pending_task_tool_use_ids:
            raise RuntimeError(
                f"SubagentStart for {agent_id} with no pending Agent "
                f"PreToolUse — parent link lost"
            )
        parent_tuid = self._pending_task_tool_use_ids.popleft()
        self._subagent_parent_tuids[agent_id] = parent_tuid
        self._subagent_start_times[agent_id] = time.time()
        self._subagent_types[agent_id] = agent_type
        await log_audit(
            self._run_id,
            "subagent_start",
            {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "parent_tool_use_id": parent_tuid,
            },
        )
        self._emit(
            {
                "event": "subagent_start",
                "data": {
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "parent_tool_use_id": parent_tuid,
                },
            }
        )
        return SyncHookJSONOutput()

    async def _hook_subagent_stop(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Clean up tracking, log final text + parent link to DB, emit event.

        last_assistant_message is the subagent's final textual response
        and is the real source for the dashboard's finalText rendering.
        parent_tool_use_id comes from the agent_id -> parent_tuid map
        populated at SubagentStart, not from the hook's tool_use_id
        param (which is an unrelated UUID).
        """
        agent_id = hook_input.get("agent_id", "")
        if not agent_id:
            raise RuntimeError("SubagentStop missing agent_id")
        parent_tuid = self._subagent_parent_tuids.pop(agent_id, None)
        if parent_tuid is None:
            raise RuntimeError(
                f"SubagentStop for {agent_id} with no recorded parent "
                f"tool_use_id — subagent_start never fired for it"
            )
        final_text = hook_input.get("last_assistant_message", "")
        self._subagent_start_times.pop(agent_id, None)
        self._subagent_last_tool.pop(agent_id, None)
        self._subagent_types.pop(agent_id, None)
        await log_audit(
            self._run_id,
            "subagent_complete",
            {
                "agent_id": agent_id,
                "parent_tool_use_id": parent_tuid,
                "final_text": final_text,
            },
        )
        self._emit(
            {
                "event": "subagent_stop",
                "data": {
                    "agent_id": agent_id,
                    "parent_tool_use_id": parent_tuid,
                },
            }
        )
        return SyncHookJSONOutput()

    async def _hook_stop(
        self,
        hook_input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        """Log agent stop to DB."""
        await log_audit(
            self._run_id,
            "agent_stop",
            {
                "reason": hook_input.get("stop_reason", "unknown"),
            },
        )
        return SyncHookJSONOutput()

    # ── Session gate MCP tools ──

    def _build_session_gate_mcp(self, config: dict) -> Any:
        """Build MCP server with end_round + end_session tools.

        `end_round` ends the current round (the Python loop will start the
        next round). `end_session` ends the whole run and is denied while
        the time lock has more than EARLY_EXIT_THRESHOLD_MIN remaining.
        """
        duration_min: float = config["duration_minutes"]
        # The run's real start time comes from bootstrap.py via the
        # config dict. Do NOT call time.time() here — this method runs
        # once per sandbox session (i.e. once per round), so a local
        # clock would reset the budget to full on every new round and
        # the time lock would never fire.
        start: float = config["start_time"]
        emit = self._emit
        session = self
        run_id = self._run_id

        @tool(
            "end_round",
            (
                "End THIS round so the Python loop can commit and start the"
                " next round. Use when the plan → build → review cycle is"
                " done for this round but the overall task is not yet"
                " complete. Does NOT end the whole run — use `end_session`"
                " for that."
            ),
            {"summary": str},
        )
        async def end_round_tool(args: dict[str, Any]) -> dict[str, Any]:
            summary = args["summary"]
            session._ended = True
            emit({"event": "end_round", "data": {"summary": summary}})
            return {"content": [{"type": "text", "text": "Round ended."}]}

        @tool(
            "end_session",
            (
                "End the ENTIRE run. Call only when there is nothing more"
                " to build, fix, or verify across any future round. Denied"
                " while the time lock has time remaining."
            ),
            {"summary": str},
        )
        async def end_session_tool(args: dict[str, Any]) -> dict[str, Any]:
            elapsed_sec = time.time() - start
            elapsed_min = elapsed_sec / SECONDS_PER_MINUTE
            remaining_min = duration_min - elapsed_min
            unlocked = (
                duration_min <= 0
                or remaining_min <= EARLY_EXIT_THRESHOLD_MIN
                or session.unlocked
            )

            if unlocked:
                await log_audit(
                    run_id,
                    "session_ended",
                    {
                        "summary": args["summary"],
                        "elapsed_minutes": round(elapsed_min, 1),
                    },
                )
                session._ended = True
                emit(
                    {
                        "event": "end_session",
                        "data": {
                            "summary": args["summary"],
                            "elapsed_minutes": round(elapsed_min, 1),
                        },
                    }
                )
                return {"content": [{"type": "text", "text": "Session ended."}]}

            await log_audit(
                run_id,
                "end_session_denied",
                {
                    "remaining_minutes": round(remaining_min, 1),
                },
            )
            emit(
                {
                    "event": "end_session_denied",
                    "data": {
                        "remaining_minutes": round(remaining_min, 1),
                    },
                }
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"SESSION LOCKED — {round(remaining_min, 1)}m remaining. "
                            "Keep working and start another round. Call `end_round` if "
                            "this round's cycle is complete."
                        ),
                    }
                ]
            }

        return create_sdk_mcp_server(
            name="session_gate",
            tools=[end_round_tool, end_session_tool],
        )
