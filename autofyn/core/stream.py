"""Stream processor: dispatches SDK events from sandbox SSE.

StreamProcessor reads events from the sandbox's SSE stream and dispatches
them to the appropriate handler. Control events (stop, pause, inject) are
checked via asyncio.wait racing against the SSE stream — zero-latency
interruption without polling.
"""

import asyncio
import logging

from utils import db
from utils.constants import LOG_PREVIEW_LIMIT
from utils.models import DispatchResult, StreamResult, RunContext
from sandbox_manager.client import SandboxClient
from core.control import ControlHandler
from core.event_bus import EventBus
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
        events: EventBus,
    ) -> None:
        self._sandbox = sandbox
        self._session_id = session_id
        self._run_context = run_context
        self._session = session
        self._tracker = tracker
        self._control = control
        self._events = events
        self._rid = run_context.run_id[:8]

    async def process(self) -> StreamResult:
        """Process sandbox SSE events until session ends.

        Races the SSE stream against control events via asyncio.wait so
        stop/pause signals take effect immediately — even when the sandbox
        is silent between tool calls or during long thinking.
        """
        result_msg: dict | None = None
        should_stop = False
        final_status: str | None = None

        stream_iter = self._sandbox.stream_events(self._session_id).__aiter__()
        control_task: asyncio.Task = asyncio.create_task(self._events.wait_for_event())
        sse_task: asyncio.Task = asyncio.create_task(self._next_sse(stream_iter))

        try:
            while True:
                done, _ = await asyncio.wait(
                    {sse_task, control_task}, return_when=asyncio.FIRST_COMPLETED,
                )

                if control_task in done:
                    action = await self._control.handle_event(control_task.result())
                    control_task = asyncio.create_task(self._events.wait_for_event())
                    if action.stop:
                        should_stop = True
                        final_status = action.final_status
                        break
                    if action.break_stream:
                        break

                if sse_task in done:
                    sse_result = sse_task.result()
                    if sse_result is None:
                        break
                    sse_task = asyncio.create_task(self._next_sse(stream_iter))
                    dispatched = await self._dispatch_event(sse_result)
                    if dispatched.result_data is not None:
                        result_msg = dispatched.result_data
                    if dispatched.should_stop:
                        should_stop = True
                        final_status = dispatched.final_status
                        break

        finally:
            sse_task.cancel()
            control_task.cancel()

        return StreamResult(
            should_stop=should_stop,
            final_status=final_status,
            session_ended=self._session.has_ended(),
            result_message=result_msg,
        )

    async def _next_sse(self, stream_iter: object) -> dict | None:
        """Get next SSE event or None if stream is exhausted."""
        try:
            return await stream_iter.__anext__()  # type: ignore[union-attr]
        except StopAsyncIteration:
            return None

    async def _dispatch_event(self, event: dict) -> DispatchResult:
        """Route a single SSE event."""
        event_type = event.get("event", "")
        data = event.get("data", {})

        if event_type == "assistant_message":
            self._handle_assistant_message(data)

        elif event_type == "rate_limit":
            action = await self._control.handle_rate_limit(data, self._run_context)
            if action.stop:
                return DispatchResult(should_stop=True, final_status=action.final_status, result_data=None)

        elif event_type == "result":
            await self._handle_result(data)
            return DispatchResult(should_stop=False, final_status=None, result_data=data)

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

        return DispatchResult.ok()

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
