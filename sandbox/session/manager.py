"""Claude SDK session lifecycle management inside the sandbox.

SessionManager starts Claude SDK sessions, streams events to the agent,
and handles message sending, interruption, and cleanup.

All DB logging (tool calls, audit events) happens directly here — no
round-trip to the agent. The agent only receives minimal SSE events
for decision-making: assistant messages, rate limits, results, and
subagent lifecycle (for stuck detection).
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import AgentDefinition
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    tool,
    create_sdk_mcp_server,
)
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    RateLimitEvent,
    StreamEvent,
    SyncHookJSONOutput,
    ToolPermissionContext,
)

from constants import (
    EARLY_EXIT_THRESHOLD_MIN,
    INPUT_SUMMARY_MAX_LEN,
    MAX_CONCURRENT_SESSIONS,
    SESSION_EVENT_QUEUE_SIZE,
    SUBAGENT_TIMEOUT_SEC,
)
from db.connection import get_session_factory
from db.models import AuditLog, ToolCall
from session.security import SecurityGate

log = logging.getLogger("sandbox.session_manager")

SECONDS_PER_MINUTE: int = 60


# ── SessionManager ──────────────────────────────────────────


class SessionManager:
    """Manages active Claude SDK sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    def active_count(self) -> int:
        """Return the number of currently active sessions."""
        return len(self._sessions)

    async def start(self, options_dict: dict) -> str:
        """Start a new Claude SDK session. Returns session_id."""
        if len(self._sessions) >= MAX_CONCURRENT_SESSIONS:
            raise RuntimeError(f"Max sessions ({MAX_CONCURRENT_SESSIONS}) reached")
        session_id = uuid.uuid4().hex[:12]
        session = _Session(session_id, options_dict, self._remove_session)
        self._sessions[session_id] = session
        session.task = asyncio.create_task(session.run())
        log.info("Session %s started", session_id)
        return session_id

    def get_event_queue(self, session_id: str) -> asyncio.Queue:
        """Get the event queue for SSE streaming."""
        return self._get(session_id).events

    async def send_message(self, session_id: str, text: str) -> None:
        """Send a follow-up query to the session."""
        s = self._get(session_id)
        if s.client:
            await s.client.query(text)

    async def interrupt(self, session_id: str) -> None:
        """Interrupt the current response."""
        s = self._get(session_id)
        if s.client:
            await s.client.interrupt()

    async def stop(self, session_id: str) -> None:
        """Stop a session and clean up."""
        session = self._sessions.pop(session_id, None)
        if session and session.task:
            session.task.cancel()

    async def stop_all(self) -> None:
        """Stop all active sessions."""
        for sid in list(self._sessions.keys()):
            await self.stop(sid)

    def _get(self, session_id: str) -> "_Session":
        """Look up a session by ID."""
        session = self._sessions.get(session_id)
        if not session:
            raise RuntimeError(f"Session {session_id} not found")
        return session

    def _remove_session(self, session_id: str) -> None:
        """Remove a finished session from the registry."""
        self._sessions.pop(session_id, None)


# ── Session ─────────────────────────────────────────────────


class _Session:
    """A single Claude SDK session running in the sandbox."""

    def __init__(
        self, session_id: str, options_dict: dict,
        cleanup_callback: Callable[[str], None],
    ):
        self.session_id = session_id
        self.options_dict = options_dict
        self._cleanup = cleanup_callback
        self.events: asyncio.Queue = asyncio.Queue(maxsize=SESSION_EVENT_QUEUE_SIZE)
        self.client: ClaudeSDKClient | None = None
        self.task: asyncio.Task | None = None
        self._ended = False
        # Hook state
        self._pre_tool_times: dict[str, float] = {}
        self._subagent_start_times: dict[str, float] = {}
        self._subagent_last_tool: dict[str, float] = {}
        self._subagent_types: dict[str, str] = {}

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
                    event = _serialize_message(message)
                    if event:
                        self._emit(event)
                    if isinstance(message, ResultMessage):
                        break
                    if self._ended:
                        break
            self._emit({"event": "session_end", "data": {}})
        except asyncio.CancelledError:
            self._emit({"event": "session_end", "data": {"reason": "cancelled"}})
        except Exception as e:
            log.error("Session %s error: %s", self.session_id, e, exc_info=True)
            self._emit({"event": "session_error", "data": {"error": str(e)}})
        finally:
            self._cleanup(self.session_id)

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
        agents = _parse_agents(agents_raw) if agents_raw else None

        return ClaudeAgentOptions(
            model=opts["model"],
            fallback_model=opts.get("fallback_model"),
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
            tool_name: str, input_data: dict, context: ToolPermissionContext,
        ) -> PermissionResultAllow | PermissionResultDeny:
            deny = gate.check_permission(tool_name, input_data)
            if deny:
                await _log_audit(self._run_id, "permission_denied", {
                    "tool_name": tool_name, "reason": deny,
                })
                return PermissionResultDeny(message=deny)
            return PermissionResultAllow(updated_input=input_data)
        return _check

    # ── SDK hooks (log to DB, emit minimal SSE for agent tracking) ──

    def _build_hooks(self) -> dict:
        """Build SDK hook registrations."""
        return {
            "PreToolUse": [HookMatcher(hooks=[self._hook_pre_tool])],
            "PostToolUse": [HookMatcher(hooks=[self._hook_post_tool])],
            "SubagentStart": [HookMatcher(hooks=[self._hook_subagent_start])],
            "SubagentStop": [HookMatcher(hooks=[self._hook_subagent_stop])],
            "Stop": [HookMatcher(hooks=[self._hook_stop])],
        }

    async def _hook_pre_tool(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
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
                    await _log_audit(self._run_id, "subagent_timeout", {
                        "agent_id": agent_id, "elapsed_seconds": int(elapsed),
                    })
                    return SyncHookJSONOutput(
                        decision="block",
                        reason=f"Subagent timed out after {int(elapsed)}s",
                    )

        self._pre_tool_times[tid] = time.time()
        role = self._subagent_types.get(agent_id, "worker") if agent_id else "worker"
        await _log_tool_call(
            self._run_id, "pre", tool_name,
            _summarize(tool_input), None, None, True, None, role,
            tid, sid, agent_id,
        )
        self._emit({"event": "tool_use", "data": {"agent_id": agent_id}})
        return SyncHookJSONOutput()

    async def _hook_post_tool(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Log post-tool to DB with duration."""
        tool_name = hook_input.get("tool_name", "unknown")
        response = hook_input.get("tool_response")
        agent_id = hook_input.get("agent_id")
        tid = tool_use_id or ""
        sid = hook_input.get("session_id")

        duration_ms = None
        if tid in self._pre_tool_times:
            duration_ms = int((time.time() - self._pre_tool_times.pop(tid)) * 1000)

        role = self._subagent_types.get(agent_id, "worker") if agent_id else "worker"
        out = _summarize(response) if response is not None else None
        await _log_tool_call(
            self._run_id, "post", tool_name,
            None, out, duration_ms, True, None, role,
            tid, sid, agent_id,
        )
        return SyncHookJSONOutput()

    async def _hook_subagent_start(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Track subagent, log to DB, emit event for agent stuck detection."""
        agent_id = hook_input.get("agent_id", "")
        agent_type = hook_input.get("agent_type", "")
        self._subagent_start_times[agent_id] = time.time()
        self._subagent_types[agent_id] = agent_type
        await _log_audit(self._run_id, "subagent_start", {
            "agent_id": agent_id, "agent_type": agent_type,
        })
        self._emit({"event": "subagent_start", "data": {
            "agent_id": agent_id, "agent_type": agent_type,
        }})
        return SyncHookJSONOutput()

    async def _hook_subagent_stop(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Clean up tracking, log to DB, emit event."""
        agent_id = hook_input.get("agent_id", "")
        self._subagent_start_times.pop(agent_id, None)
        self._subagent_last_tool.pop(agent_id, None)
        self._subagent_types.pop(agent_id, None)
        await _log_audit(self._run_id, "subagent_complete", {"agent_id": agent_id})
        self._emit({"event": "subagent_stop", "data": {"agent_id": agent_id}})
        return SyncHookJSONOutput()

    async def _hook_stop(
        self, hook_input: HookInput, tool_use_id: str | None, context: HookContext,
    ) -> SyncHookJSONOutput:
        """Log agent stop to DB."""
        await _log_audit(self._run_id, "agent_stop", {
            "reason": hook_input.get("stop_reason", "unknown"),
        })
        return SyncHookJSONOutput()

    # ── Session gate MCP tool ──

    def _build_session_gate_mcp(self, config: dict) -> Any:
        """Build MCP server with end_session tool for time-locked sessions."""
        duration_min: float = config["duration_minutes"]
        start = time.time()
        emit = self._emit
        session = self
        run_id = self._run_id

        @tool(
            "end_session",
            "End the current session. Denied if the time lock has not expired.",
            {"summary": str, "changes_made": int},
        )
        async def end_session_tool(args: dict[str, Any]) -> dict[str, Any]:
            elapsed_sec = time.time() - start
            elapsed_min = elapsed_sec / SECONDS_PER_MINUTE
            remaining_min = duration_min - elapsed_min
            unlocked = duration_min <= 0 or remaining_min <= EARLY_EXIT_THRESHOLD_MIN

            if unlocked:
                await _log_audit(run_id, "session_ended", {
                    "summary": args["summary"],
                    "changes_made": args["changes_made"],
                    "elapsed_minutes": round(elapsed_min, 1),
                })
                session._ended = True
                emit({"event": "end_session", "data": {
                    "summary": args["summary"],
                    "changes_made": args["changes_made"],
                    "elapsed_minutes": round(elapsed_min, 1),
                }})
                return {"content": [{"type": "text", "text": "Session ended."}]}

            await _log_audit(run_id, "end_session_denied", {
                "remaining_minutes": round(remaining_min, 1),
            })
            emit({"event": "end_session_denied", "data": {
                "remaining_minutes": round(remaining_min, 1),
            }})
            return {"content": [{"type": "text", "text": (
                f"SESSION LOCKED — {round(remaining_min, 1)}m remaining. "
                "Continue working. The planner will tell you when to stop."
            )}]}

        return create_sdk_mcp_server(name="session_gate", tools=[end_session_tool])


# ── DB helpers (direct writes, no round-trip to agent) ──────


async def _log_tool_call(
    run_id: str, phase: str, tool_name: str,
    input_data: dict | None, output_data: dict | None,
    duration_ms: int | None, permitted: bool, deny_reason: str | None,
    agent_role: str, tool_use_id: str | None,
    session_id: str | None, agent_id: str | None,
) -> None:
    """Insert a tool call row into the database."""
    try:
        async with get_session_factory()() as s:
            s.add(ToolCall(
                run_id=run_id, phase=phase, tool_name=tool_name,
                input_data=input_data, output_data=output_data,
                duration_ms=duration_ms, permitted=permitted,
                deny_reason=deny_reason, agent_role=agent_role,
                tool_use_id=tool_use_id, session_id=session_id,
                agent_id=agent_id,
            ))
            await s.commit()
    except Exception as e:
        log.warning("Failed to log tool call: %s", e)


async def _log_audit(run_id: str, event_type: str, details: dict) -> None:
    """Insert an audit log row into the database."""
    try:
        async with get_session_factory()() as s:
            s.add(AuditLog(run_id=run_id, event_type=event_type, details=details))
            await s.commit()
    except Exception as e:
        log.warning("Failed to log audit event: %s", e)


# ── Serialization helpers ───────────────────────────────────


def _parse_agents(raw: dict[str, dict]) -> dict[str, AgentDefinition]:
    """Convert plain dicts from the agent into AgentDefinition dataclasses."""
    return {
        name: AgentDefinition(
            description=defn["description"],
            prompt=defn["prompt"],
            model=defn.get("model"),
            tools=defn.get("tools"),
        )
        for name, defn in raw.items()
    }


def _summarize(data: Any) -> dict:
    """Truncate large values in tool input/output for DB storage as JSONB."""
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


def _serialize_message(message: object) -> dict | None:
    """Convert SDK message to a JSON-serializable event dict."""
    if isinstance(message, StreamEvent):
        return {"event": "stream_event", "data": {"event": message.event or {}}}
    if isinstance(message, AssistantMessage):
        blocks = []
        for block in message.content:
            if isinstance(block, TextBlock):
                blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ThinkingBlock):
                blocks.append({"type": "thinking", "thinking": block.thinking})
            elif isinstance(block, ToolUseBlock):
                blocks.append({"type": "tool_use", "id": block.id,
                               "name": block.name, "input": block.input})
        return {"event": "assistant_message", "data": {"content": blocks, "usage": message.usage}}
    if isinstance(message, RateLimitEvent):
        info = message.rate_limit_info
        return {"event": "rate_limit", "data": {
            "status": info.status, "resets_at": info.resets_at, "utilization": info.utilization,
        }}
    if isinstance(message, ResultMessage):
        return {"event": "result", "data": {
            "session_id": message.session_id, "total_cost_usd": message.total_cost_usd,
            "num_turns": message.num_turns, "usage": message.usage,
        }}
    return None
