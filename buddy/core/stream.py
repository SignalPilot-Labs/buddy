"""Stream processor: dispatches one round of SDK messages.

StreamProcessor handles the raw SDK message loop — StreamEvent, AssistantMessage,
RateLimitEvent, ResultMessage. It knows nothing about planner/worker or round iteration.
"""

import logging
import time

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)
from claude_agent_sdk.types import RateLimitEvent, StreamEvent

from utils import db
from utils.constants import AUDIT_TEXT_LIMIT, LOG_PREVIEW_LIMIT, TEXT_CHUNK_LIMIT
from utils.models import RoundResult, RunContext
from utils.prompts import PromptLoader
from core.event_bus import EventBus
from tools.session import SessionGate

log = logging.getLogger("core.stream")


class StreamProcessor:
    """Processes one round of SDK messages. Returns a RoundResult.

    Public API:
        process(round_num, is_planning) -> RoundResult
    """

    def __init__(
        self, client, ctx: RunContext, session: SessionGate,
        events: EventBus, prompts: PromptLoader,
        model: str, fallback_model: str | None,
    ):
        self._client = client
        self._ctx = ctx
        self._session = session
        self._events = events
        self._prompts = prompts
        self._model = model
        self._fallback_model = fallback_model

    async def process(self, round_num: int, is_planning: bool) -> RoundResult:
        """Process one round of SDK messages."""
        tools: list[str] = []
        chunks: list[str] = []
        result_msg = None
        should_stop = False
        final_status: str | None = None

        async for message in self._client.receive_response():
            action = await self._check_event(is_planning)
            if action == "stop":
                should_stop = True
                final_status = "stopped"
                break
            if action == "break":
                break

            if isinstance(message, StreamEvent):
                await self._log_delta(message)
                continue

            if isinstance(message, AssistantMessage):
                self._collect_content(message, tools, chunks, is_planning)
                self._accumulate_usage(message)

            elif isinstance(message, RateLimitEvent) and not is_planning:
                status = await self._handle_rate_limit(message)
                if status:
                    should_stop = True
                    final_status = status
                    break

            elif isinstance(message, ResultMessage):
                result_msg = message
                await self._handle_result(message, round_num)

        return RoundResult(
            should_stop=should_stop, final_status=final_status,
            session_ended=self._session.has_ended(),
            result_message=result_msg,
            round_tools=tools, round_text_chunks=chunks,
        )

    # ── Event Handling ──

    async def _check_event(self, is_planning: bool) -> str | None:
        """Check for mid-round events. Returns action or None."""
        event = await self._events.drain()
        if not event:
            return None

        kind = event["event"]
        run_id = self._ctx.run_id

        if kind == "stop":
            log.info("INSTANT STOP")
            await self._client.interrupt()
            await db.log_audit(run_id, "stop_requested", {
                "reason": event.get("payload", "Operator stop"), "instant": True,
            })
            return "stop"

        if kind == "pause" and not is_planning:
            await self._client.interrupt()
            async for _ in self._client.receive_response():
                pass
            result = await self._events.handle_pause(run_id)
            if result == "stop":
                return "stop"
            if result == "resume":
                await self._client.query(self._prompts.build_continuation_prompt())
                return "break"
            if result.startswith("inject:"):
                await self._client.query(result[7:])
                return "break"
            if result == "unlock":
                self._session.force_unlock()
                await db.log_audit(run_id, "session_unlocked", {})

        if kind == "unlock":
            self._session.force_unlock()
            await db.log_audit(run_id, "session_unlocked", {})

        if kind == "inject" and not is_planning:
            await db.log_audit(run_id, "prompt_injected", {
                "prompt": event.get("payload", ""), "delivery": "queued",
            })

        if kind == "stuck_recovery" and not is_planning:
            stuck_info = event.get("payload", "[]")
            log.info("STUCK RECOVERY: interrupting for stuck subagents")
            await self._client.interrupt()
            async for _ in self._client.receive_response():
                pass
            recovery = (
                "IMPORTANT: One or more subagents got stuck and had to be killed. "
                f"Stuck agent details: {stuck_info}\n\n"
                "Please manually achieve what those subagents were supposed to do, "
                "or break the task into smaller, simpler parts. "
                "Do NOT re-spawn the same agent with the same task."
            )
            await db.log_audit(run_id, "stuck_recovery", {
                "stuck_info": stuck_info, "recovery_prompt": recovery,
            })
            await self._client.query(recovery)
            return "break"

        return None

    # ── Message Handlers ──

    async def _log_delta(self, message: StreamEvent) -> None:
        """Log text/thinking deltas."""
        event_data = message.event or {}
        if event_data.get("type") != "content_block_delta":
            return
        delta = event_data.get("delta", {})
        dtype = delta.get("type", "")
        if dtype == "text_delta" and delta.get("text"):
            await db.log_audit(self._ctx.run_id, "llm_text", {
                "text": delta["text"][:AUDIT_TEXT_LIMIT], "agent_role": self._ctx.agent_role,
            })
        elif dtype == "thinking_delta" and delta.get("thinking"):
            await db.log_audit(self._ctx.run_id, "llm_thinking", {
                "text": delta["thinking"][:AUDIT_TEXT_LIMIT], "agent_role": self._ctx.agent_role,
            })

    def _collect_content(
        self, message: AssistantMessage, tools: list[str], chunks: list[str], is_planning: bool,
    ) -> None:
        """Extract text chunks and tool names."""
        tag = "[PLANNER] " if is_planning else ""
        for block in message.content:
            if isinstance(block, TextBlock):
                log.info("%s%s", tag, block.text[:LOG_PREVIEW_LIMIT].replace("\n", " "))
                chunks.append(block.text[:TEXT_CHUNK_LIMIT])
            elif isinstance(block, ThinkingBlock):
                log.info("%s[thinking] %s...", tag, block.thinking[:100])
            elif isinstance(block, ToolUseBlock):
                log.info("Tool: %s", block.name)
                tools.append(block.name)

    def _accumulate_usage(self, message: AssistantMessage) -> None:
        """Add usage to run context."""
        if message.usage:
            self._ctx.total_input_tokens += message.usage.get("input_tokens", 0)
            self._ctx.total_output_tokens += message.usage.get("output_tokens", 0)

    async def _handle_result(self, message: ResultMessage, round_num: int) -> None:
        """Save session ID, update costs, log round."""
        if message.session_id:
            await db.save_session_id(self._ctx.run_id, message.session_id)
        if message.total_cost_usd:
            self._ctx.total_cost = message.total_cost_usd
        if message.usage:
            self._ctx.total_input_tokens = message.usage.get("input_tokens", self._ctx.total_input_tokens)
            self._ctx.total_output_tokens = message.usage.get("output_tokens", self._ctx.total_output_tokens)
        await db.log_audit(self._ctx.run_id, "round_complete", {
            "round": round_num + 1, "turns": message.num_turns,
            "cost_usd": message.total_cost_usd,
            "elapsed_minutes": round(self._session.elapsed_minutes(), 1),
        })

    async def _handle_rate_limit(self, message: RateLimitEvent) -> str | None:
        """Handle rate limit. Returns final_status if should stop."""
        info = message.rate_limit_info
        run_id = self._ctx.run_id
        await db.log_audit(run_id, "rate_limit", {
            "status": info.status, "resets_at": info.resets_at, "utilization": info.utilization,
        })
        if info.status != "rejected":
            return None

        resets_at = info.resets_at
        wait_sec = max(0, resets_at - time.time()) if resets_at else 0

        if self._fallback_model and self._fallback_model != self._model:
            log.info("Rate limited on %s, fallback to %s", self._model, self._fallback_model)
            await db.log_audit(run_id, "rate_limit_fallback", {
                "primary_model": self._model, "fallback_model": self._fallback_model,
            })
            return None

        log.info("Rate limited. Resets in %dm.", int(wait_sec / 60))
        await db.update_run_status(run_id, "rate_limited")
        if resets_at:
            await db.save_rate_limit_reset(run_id, int(resets_at))
        await db.log_audit(run_id, "rate_limit_paused", {
            "resets_at": resets_at, "wait_seconds": int(wait_sec) if resets_at else None,
        })
        return "rate_limited"
