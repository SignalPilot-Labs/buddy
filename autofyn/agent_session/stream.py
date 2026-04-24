"""StreamDispatcher — route sandbox SSE events to handlers.

Pure logic: consumes one event, mutates the RunContext, returns a
StreamSignal telling the session runner what action to take. No
asyncio.wait, no inbox, no sandbox interaction — those belong to the
runner. The StreamSignal dataclass lives in utils.models.
"""

import logging

from agent_session.tracker import SubagentTracker
from utils import db
from utils.db_logging import log_audit
from utils.constants import (
    LOG_PREVIEW_LIMIT,
    USAGE_EMIT_INTERVAL,
    cost_per_cache_read,
    cost_per_cache_write,
    cost_per_input,
    cost_per_output,
)
from utils.models import RunContext, StreamSignal

log = logging.getLogger("session.stream")


class StreamDispatcher:
    """Dispatches sandbox SSE events. One instance per round.

    Public API:
        dispatch(event) -> StreamSignal
    """

    def __init__(
        self,
        run: RunContext,
        round_number: int,
        tracker: SubagentTracker,
    ) -> None:
        self._run = run
        self._round_number = round_number
        self._tracker = tracker
        self._rid = run.run_id[:8]
        # Snapshot everything at round start so running cost estimates
        # during this round only measure THIS round's delta — prior
        # rounds' cost and tokens are already accounted for in run.*.
        self._cost_baseline: float = run.total_cost
        self._input_baseline: int = run.total_input_tokens
        self._output_baseline: int = run.total_output_tokens
        self._cache_create_baseline: int = run.cache_creation_input_tokens
        self._cache_read_baseline: int = run.cache_read_input_tokens
        self._message_count: int = 0
        self._latest_context_tokens: int = 0
        self._tools_in_flight: int = 0

    def has_tools_in_flight(self) -> bool:
        """True if any tool call is currently executing."""
        return self._tools_in_flight > 0 or self._tracker.has_tools_in_flight()

    def has_active_subagents(self) -> bool:
        """True if any subagents are currently tracked as active."""
        return self._tracker.active_count() > 0

    async def dispatch(self, event: dict) -> StreamSignal:
        """Handle one SSE event. Mutates RoundState, returns a signal."""
        kind = event.get("event", "")
        data = event.get("data", {})

        if kind == "assistant_message":
            await self._handle_assistant_message(data)
            return StreamSignal(kind="continue")

        if kind == "tool_use":
            self._handle_tool_use(data)
            return StreamSignal(kind="continue")

        if kind == "tool_done":
            self._handle_tool_done(data)
            return StreamSignal(kind="continue")

        if kind == "subagent_start":
            self._handle_subagent_start(data)
            return StreamSignal(kind="continue")

        if kind == "subagent_stop":
            self._handle_subagent_stop(data)
            return StreamSignal(kind="subagent_boundary")

        if kind == "rate_limit":
            # The SDK emits `rate_limit` events for THREE statuses:

            status = data.get("status")
            if status == "rejected":
                log.warning(
                    "[%s] rate limit rejected — SDK will retry (resets_at=%s, utilization=%s)",
                    self._rid,
                    data.get("resets_at"),
                    data.get("utilization"),
                )
                return StreamSignal(kind="rate_limit_info", rate_limit_data=data)
            if status == "allowed_warning":
                log.info(
                    "[%s] rate limit warning (resets_at=%s, utilization=%s)",
                    self._rid,
                    data.get("resets_at"),
                    data.get("utilization"),
                )
            return StreamSignal(kind="continue")

        if kind == "result":
            await self._handle_result(data)
            return StreamSignal(kind="round_complete")

        if kind == "end_round":
            round_summary = data.get("round_summary") or ""
            session_summary = data.get("session_summary") or ""
            log.info("[%s] end_round: %s", self._rid, round_summary[:80])
            return StreamSignal(
                kind="round_complete",
                round_summary=round_summary,
                session_summary=session_summary,
            )

        if kind == "end_session":
            log.info("[%s] end_session received", self._rid)
            return StreamSignal(
                kind="run_ended",
                round_summary=data.get("round_summary"),
                session_summary=data.get("session_summary"),
            )

        if kind == "end_session_denied":
            log.info(
                "[%s] end_session denied: %sm remaining",
                self._rid,
                data.get("remaining_minutes", "?"),
            )
            return StreamSignal(kind="continue")

        if kind == "session_end":
            return StreamSignal(kind="round_complete")

        if kind == "session_error":
            error_msg = data.get("error", "unknown")
            log.error("[%s] session error: %s", self._rid, error_msg)
            return StreamSignal(kind="session_error", error=error_msg)

        return StreamSignal(kind="continue")

    # ── Handlers ───────────────────────────────────────────────────────

    async def _handle_assistant_message(self, data: dict) -> None:
        """Log text/thinking blocks and accumulate token usage."""
        run_id = self._run.run_id
        for block in data.get("content", []):
            block_type = block.get("type", "")
            if block_type == "text":
                text = block.get("text", "")
                log.info(
                    "[%s] %s", self._rid, text[:LOG_PREVIEW_LIMIT].replace("\n", " ")
                )
                if text.strip():
                    await log_audit(
                        run_id,
                        "llm_text",
                        {
                            "text": text,
                            "agent_role": self._run.agent_role,
                        },
                    )
            elif block_type == "thinking":
                thinking = block.get("thinking", "")
                log.info("[%s] [thinking] %s...", self._rid, thinking[:100])
                if thinking.strip():
                    await log_audit(
                        run_id,
                        "llm_thinking",
                        {
                            "text": thinking,
                            "agent_role": self._run.agent_role,
                        },
                    )
            elif block_type == "tool_use":
                log.info("[%s] Tool: %s", self._rid, block.get("name", ""))
        await self._accumulate_usage(data)

    def _handle_subagent_start(self, data: dict) -> None:
        """Record a subagent starting in the tracker."""
        agent_id = data.get("agent_id", "")
        agent_type = data.get("agent_type", "")
        if agent_id:
            self._tracker.record_start(agent_id, agent_type)

    def _handle_subagent_stop(self, data: dict) -> None:
        """Record a subagent stopping in the tracker."""
        agent_id = data.get("agent_id", "")
        if agent_id:
            self._tracker.record_stop(agent_id)

    def _handle_tool_use(self, data: dict) -> None:
        """Track tool start for both subagents and orchestrator."""
        self._tools_in_flight += 1
        agent_id: str | None = data.get("agent_id")
        self._tracker.record_tool_use(agent_id)

    def _handle_tool_done(self, data: dict) -> None:
        """Track tool completion for both subagents and orchestrator."""
        self._tools_in_flight = max(0, self._tools_in_flight - 1)
        agent_id: str | None = data.get("agent_id")
        self._tracker.record_tool_done(agent_id)

    async def _handle_result(self, data: dict) -> None:
        """Persist the SDK session id and settle cost.

        ResultMessage carries the authoritative cost for THIS round's
        session. We add it to the prior-rounds baseline and rebase so any
        late assistant_messages in this round (rare) can't double-count.
        """
        run_id = self._run.run_id
        session_id = data.get("session_id")
        if session_id:
            await db.save_session_id(run_id, session_id)
        round_cost = data.get("total_cost_usd")
        if round_cost is not None:
            self._run.total_cost = self._cost_baseline + round_cost
            self._cost_baseline = self._run.total_cost
            self._input_baseline = self._run.total_input_tokens
            self._output_baseline = self._run.total_output_tokens
            self._cache_create_baseline = self._run.cache_creation_input_tokens
            self._cache_read_baseline = self._run.cache_read_input_tokens
        await self._persist_cost()

    async def _accumulate_usage(self, data: dict) -> None:
        """Accumulate token usage and emit a throttled usage audit event.

        Running cost estimate uses ONLY this round's delta (current totals
        minus baselines captured at round start) added to the prior-rounds
        baseline. ResultMessage replaces this estimate with the SDK's
        authoritative cost for the round.
        """
        usage = data.get("usage")
        if usage:
            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            cache_create = usage.get("cache_creation_input_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            self._latest_context_tokens = inp + out + cache_create + cache_read
            self._run.total_input_tokens += inp
            self._run.total_output_tokens += out
            self._run.cache_creation_input_tokens += cache_create
            self._run.cache_read_input_tokens += cache_read
            round_input = self._run.total_input_tokens - self._input_baseline
            round_output = self._run.total_output_tokens - self._output_baseline
            round_cache_create = (
                self._run.cache_creation_input_tokens - self._cache_create_baseline
            )
            round_cache_read = (
                self._run.cache_read_input_tokens - self._cache_read_baseline
            )
            self._run.total_cost = self._cost_baseline + (
                round_input * cost_per_input()
                + round_output * cost_per_output()
                + round_cache_create * cost_per_cache_write()
                + round_cache_read * cost_per_cache_read()
            )
        self._message_count += 1
        if self._message_count % USAGE_EMIT_INTERVAL == 0:
            await log_audit(
                self._run.run_id,
                "usage",
                {
                    "context_tokens": self._latest_context_tokens,
                    "total_input_tokens": self._run.total_input_tokens,
                    "total_output_tokens": self._run.total_output_tokens,
                    "cache_creation_input_tokens": self._run.cache_creation_input_tokens,
                    "cache_read_input_tokens": self._run.cache_read_input_tokens,
                    "total_cost_usd": self._run.total_cost,
                },
            )
            await self._persist_cost()

    async def _persist_cost(self) -> None:
        """Write current totals to the runs table."""
        r = self._run
        await db.update_run_cost(
            r.run_id,
            r.total_cost,
            r.total_input_tokens,
            r.total_output_tokens,
            r.cache_creation_input_tokens,
            r.cache_read_input_tokens,
            self._latest_context_tokens,
        )
