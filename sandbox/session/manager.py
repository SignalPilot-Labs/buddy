"""Claude SDK session lifecycle management inside the sandbox.

SessionManager starts Claude SDK sessions, streams events to the agent,
and handles message sending, interruption, and cleanup.

All DB logging (tool calls, audit events) happens directly here — no
round-trip to the agent. The agent only receives minimal SSE events
for decision-making: assistant messages, rate limits, results, and
subagent lifecycle (for stuck detection).
"""

import asyncio
import logging
import uuid
from typing import Callable

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import HookMatcher

from constants import MAX_CONCURRENT_SESSIONS, SESSION_EVENT_QUEUE_SIZE
from session.gate import build_session_gate_mcp
from session.hooks import HookHandlers
from session.logging import log_audit
from session.security import SecurityGate
from session.serialization import parse_agents, serialize_message
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

log = logging.getLogger("sandbox.session_manager")


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
        self,
        session_id: str,
        options_dict: dict,
        cleanup_callback: Callable[[str], None],
    ):
        self.session_id = session_id
        self.options_dict = options_dict
        self._cleanup = cleanup_callback
        self.events: asyncio.Queue = asyncio.Queue(maxsize=SESSION_EVENT_QUEUE_SIZE)
        self.client: ClaudeSDKClient | None = None
        self.task: asyncio.Task | None = None

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
        gate = SecurityGate(opts.get("github_repo", ""))
        mcp = dict(opts.get("mcp_servers") or {})
        gate_cfg = opts.get("session_gate")
        if gate_cfg:
            mcp["session_gate"] = build_session_gate_mcp(gate_cfg, self._run_id, self._emit)

        agents_raw = opts.get("agents")
        agents = parse_agents(agents_raw) if agents_raw else None

        hook_handlers = HookHandlers(self._run_id, self._emit)
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
            hooks=_build_hooks(hook_handlers),
        )

    def _permission_callback(self, gate: SecurityGate) -> Callable:
        """Create permission callback bound to a SecurityGate."""
        async def _check(
            tool_name: str,
            input_data: dict,
            context: ToolPermissionContext,
        ) -> PermissionResultAllow | PermissionResultDeny:
            deny = gate.check_permission(tool_name, input_data)
            if deny:
                await log_audit(self._run_id, "permission_denied", {
                    "tool_name": tool_name, "reason": deny,
                })
                return PermissionResultDeny(message=deny)
            return PermissionResultAllow(updated_input=input_data)
        return _check


# ── Hook registration ────────────────────────────────────────


def _build_hooks(handlers: HookHandlers) -> dict:
    """Build SDK hook registrations from a HookHandlers instance."""
    return {
        "PreToolUse": [HookMatcher(hooks=[handlers.hook_pre_tool])],
        "PostToolUse": [HookMatcher(hooks=[handlers.hook_post_tool])],
        "SubagentStart": [HookMatcher(hooks=[handlers.hook_subagent_start])],
        "SubagentStop": [HookMatcher(hooks=[handlers.hook_subagent_stop])],
        "Stop": [HookMatcher(hooks=[handlers.hook_stop])],
    }
