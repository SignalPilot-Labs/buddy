"""SSE event dispatcher: routes sandbox events to handlers.

Pure business logic — no asyncio.wait, no EventBus, no control handler.
Returns DispatchResult so the session runner can orchestrate side effects.
"""

import logging

from utils import db
from utils.constants import LOG_PREVIEW_LIMIT, USAGE_EMIT_INTERVAL
from utils.models import DispatchResult, RunContext
from tools.session import SessionGate
from tools.subagent_tracker import SubagentTracker

log = logging.getLogger("core.dispatch")


class SSEDispatcher:
    """Routes SSE events to handlers. Mutates RunContext with cost/tokens.

    Public API:
        dispatch(event) -> DispatchResult
    """

    def __init__(
        self,
        run_context: RunContext,
        session: SessionGate,
        tracker: SubagentTracker,
    ) -> None:
        self._run_context = run_context
        self._session = session
        self._tracker = tracker
        self._rid = run_context.run_id[:8]
        self._message_count: int = 0
        self._cost_baseline: float = run_context.total_cost
        self._latest_input: int = 0
        self._latest_context_tokens: int = 0

    async def dispatch(self, event: dict) -> DispatchResult:
        """Route a single SSE event. Returns result for session runner to act on."""
        event_type = event.get("event", "")
        data = event.get("data", {})

        if event_type == "assistant_message":
            await self._handle_assistant_message(data)

        elif event_type == "rate_limit":
            return DispatchResult(rate_limit_data=data)

        elif event_type == "result":
            await self._handle_result(data)
            return DispatchResult(result_data=data)

        elif event_type == "subagent_start":
            self._handle_subagent_start(data)

        elif event_type == "subagent_stop":
            self._handle_subagent_stop(data)
            return DispatchResult(subagent_completed=True)

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

    async def _handle_assistant_message(self, data: dict) -> None:
        """Log assistant message content, write to DB for dashboard, accumulate usage."""
        run_id = self._run_context.run_id
        for block in data.get("content", []):
            block_type = block.get("type", "")
            if block_type == "text":
                text = block.get("text", "")
                log.info("[%s] %s", self._rid,
                         text[:LOG_PREVIEW_LIMIT].replace("\n", " "))
                if text.strip():
                    await db.log_audit(run_id, "llm_text", {
                        "text": text, "agent_role": self._run_context.agent_role,
                    })
            elif block_type == "thinking":
                thinking = block.get("thinking", "")
                log.info("[%s] [thinking] %s...",
                         self._rid, thinking[:100])
                if thinking.strip():
                    await db.log_audit(run_id, "llm_thinking", {
                        "text": thinking, "agent_role": self._run_context.agent_role,
                    })
            elif block_type == "tool_use":
                log.info("[%s] Tool: %s", self._rid, block.get("name", ""))
        await self._accumulate_usage(data)

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
        """Save session ID, update cost tracking, and persist to DB."""
        run_id = self._run_context.run_id
        session_id = data.get("session_id")
        if session_id:
            await db.save_session_id(run_id, session_id)
        cost = data.get("total_cost_usd")
        if cost:
            self._run_context.total_cost = self._cost_baseline + cost
        await db.log_audit(run_id, "round_complete", {
            "turns": data.get("num_turns"),
            "cost_usd": cost,
            "elapsed_minutes": round(self._session.elapsed_minutes(), 1),
        })
        await db.update_run_cost(
            run_id,
            self._run_context.total_cost,
            self._run_context.total_input_tokens,
            self._run_context.total_output_tokens,
            self._run_context.cache_creation_input_tokens,
            self._run_context.cache_read_input_tokens,
        )

    async def _accumulate_usage(self, data: dict) -> None:
        """Add per-message usage to run context. Emits throttled usage audit events."""
        usage = data.get("usage")
        if usage:
            self._latest_input = usage.get("input_tokens", 0)
            self._run_context.total_input_tokens += self._latest_input
            self._run_context.total_output_tokens += usage.get("output_tokens", 0)
            self._run_context.cache_creation_input_tokens += usage.get("cache_creation_input_tokens", 0)
            self._run_context.cache_read_input_tokens += usage.get("cache_read_input_tokens", 0)
        self._message_count += 1
        if self._message_count % USAGE_EMIT_INTERVAL == 0:
            await db.log_audit(self._run_context.run_id, "usage", {
                "context_tokens": self._latest_input,
                "total_input_tokens": self._run_context.total_input_tokens,
                "total_output_tokens": self._run_context.total_output_tokens,
                "cache_creation_input_tokens": self._run_context.cache_creation_input_tokens,
                "cache_read_input_tokens": self._run_context.cache_read_input_tokens,
                "total_cost_usd": self._run_context.total_cost,
            })
