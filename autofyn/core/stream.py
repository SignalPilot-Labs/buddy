"""Stream processor: dispatches SDK events from sandbox SSE.

StreamProcessor reads events from the sandbox's SSE stream and dispatches
them to the appropriate handler. Control events (stop, pause, inject) are
delegated to ControlHandler. SSE dispatch is the only responsibility.
"""

import logging

from utils import db
from utils.constants import LOG_PREVIEW_LIMIT
from utils.models import StreamResult, RunContext
from sandbox_manager.client import SandboxClient
from core.control import ControlHandler
from tools.session import SessionGate
from tools.subagent_tracker import SubagentTracker

log = logging.getLogger("core.stream")


class StreamProcessor:
    """Iterates sandbox SSE events and dispatches to handlers.

    Public API:
        process() -> StreamResult
    """

    def __init__(
        self,
        sandbox: SandboxClient,
        session_id: str,
        run_context: RunContext,
        session: SessionGate,
        tracker: SubagentTracker,
        control: ControlHandler,
    ) -> None:
        self._sandbox = sandbox
        self._session_id = session_id
        self._run_context = run_context
        self._session = session
        self._tracker = tracker
        self._control = control
        self._rid = run_context.run_id[:8]

    async def process(self) -> StreamResult:
        """Process sandbox SSE events until session ends."""
        result_msg: dict | None = None
        should_stop = False
        final_status: str | None = None

        async for event in self._sandbox.stream_events(self._session_id):
            action = await self._control.check_control_event()
            if action.stop:
                should_stop = True
                final_status = action.final_status
                break
            if action.break_stream:
                break

            event_type = event.get("event", "")
            data = event.get("data", {})

            if event_type == "assistant_message":
                self._handle_assistant_message(data)

            elif event_type == "rate_limit":
                action = await self._control.handle_rate_limit(
                    data, self._run_context,
                )
                if action.stop:
                    should_stop = True
                    final_status = action.final_status
                    break

            elif event_type == "result":
                result_msg = data
                await self._handle_result(data)

            elif event_type == "subagent_start":
                self._handle_subagent_start(data)

            elif event_type == "subagent_stop":
                self._handle_subagent_stop(data)
                await self._control.on_subagent_complete(self._run_context)

            elif event_type == "tool_use":
                self._handle_tool_use(data)

            elif event_type == "end_session":
                self._session.mark_ended()

            elif event_type == "end_session_denied":
                log.info("[%s] end_session denied: %sm remaining",
                         self._rid, data.get("remaining_minutes", "?"))

            elif event_type in ("session_end", "session_error"):
                if event_type == "session_error":
                    log.error("[%s] Session error: %s",
                              self._rid, data.get("error", "unknown"))
                break

        return StreamResult(
            should_stop=should_stop,
            final_status=final_status,
            session_ended=self._session.has_ended(),
            result_message=result_msg,
        )

    # ── Event Handlers ──

    def _handle_assistant_message(self, data: dict) -> None:
        """Log assistant message content and accumulate usage."""
        for block in data.get("content", []):
            block_type = block.get("type", "")
            if block_type == "text":
                text = block.get("text", "")
                log.info("[%s] %s", self._rid,
                         text[:LOG_PREVIEW_LIMIT].replace("\n", " "))
            elif block_type == "thinking":
                log.info("[%s] [thinking] %s...",
                         self._rid, block.get("thinking", "")[:100])
            elif block_type == "tool_use":
                log.info("[%s] Tool: %s", self._rid, block.get("name", ""))
        self._accumulate_usage(data)

    def _handle_subagent_start(self, data: dict) -> None:
        """Track subagent start."""
        agent_id = data.get("agent_id", "")
        agent_type = data.get("agent_type", "")
        if agent_id:
            self._tracker.track_subagent_start(agent_id, agent_type)

    def _handle_subagent_stop(self, data: dict) -> None:
        """Track subagent stop."""
        agent_id = data.get("agent_id", "")
        if agent_id:
            self._tracker.track_subagent_stop(agent_id)

    def _handle_tool_use(self, data: dict) -> None:
        """Track tool use for stuck detection."""
        agent_id = data.get("agent_id")
        if agent_id:
            self._tracker.track_tool_use(agent_id)

    async def _handle_result(self, data: dict) -> None:
        """Save session ID and update cost tracking."""
        run_id = self._run_context.run_id
        session_id = data.get("session_id")
        if session_id:
            await db.save_session_id(run_id, session_id)
        cost = data.get("total_cost_usd")
        if cost:
            self._run_context.total_cost = cost
        usage = data.get("usage")
        if usage:
            self._run_context.total_input_tokens = usage.get(
                "input_tokens", self._run_context.total_input_tokens,
            )
            self._run_context.total_output_tokens = usage.get(
                "output_tokens", self._run_context.total_output_tokens,
            )
        await db.log_audit(run_id, "round_complete", {
            "turns": data.get("num_turns"),
            "cost_usd": cost,
            "elapsed_minutes": round(self._session.elapsed_minutes(), 1),
        })

    def _accumulate_usage(self, data: dict) -> None:
        """Add usage to run context."""
        usage = data.get("usage")
        if usage:
            self._run_context.total_input_tokens += usage.get("input_tokens", 0)
            self._run_context.total_output_tokens += usage.get("output_tokens", 0)
