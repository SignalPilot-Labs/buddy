"""Stream processor: dispatches one round of SDK messages.

StreamProcessor handles the raw SDK message loop — StreamEvent, AssistantMessage,
RateLimitEvent, ResultMessage. It knows nothing about planner/worker or round iteration.
"""

import asyncio
import json
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
from utils.constants import AUDIT_TEXT_LIMIT, LOG_PREVIEW_LIMIT, RATE_LIMIT_MAX_WAIT_SEC, RATE_LIMIT_SLEEP_BUFFER_SEC, TEXT_CHUNK_LIMIT
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
        inject_payloads: list[str] = []

        async for message in self._client.receive_response():
            action = await self._check_event(is_planning)
            if action == "stop":
                should_stop = True
                final_status = "stopped"
                break
            if action == "break":
                break
            if action and action.startswith("inject:"):
                inject_payloads.append(action[7:])

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
            pending_injects=inject_payloads,
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
                return None

        elif kind == "unlock":
            self._session.force_unlock()
            await db.log_audit(run_id, "session_unlocked", {})

        elif kind == "inject" and not is_planning:
            prompt = event.get("payload", "")
            await db.log_audit(run_id, "prompt_injected", {
                "prompt": prompt, "delivery": "queued",
            })
            return f"inject:{prompt}"

        elif kind == "stuck_recovery" and not is_planning:
            stuck_info = event.get("payload", "[]")
            log.info("STUCK RECOVERY: interrupting for stuck subagents")
            await self._client.interrupt()
            async for _ in self._client.receive_response():
                pass

            # Parse stuck agent types for a more actionable recovery prompt
            try:
                stuck_agents = json.loads(stuck_info)
                agent_types = [a.get("agent_type", "unknown") for a in stuck_agents]
                types_str = ", ".join(agent_types) if agent_types else "unknown"
            except (json.JSONDecodeError, TypeError):
                types_str = "unknown"

            recovery = (
                f"IMPORTANT: Stuck subagent(s) detected and killed: [{types_str}]. "
                f"Details: {stuck_info}\n\n"
                "Recovery steps:\n"
                "1. Do NOT re-spawn the same agent with the same task\n"
                "2. Break the work into smaller, simpler parts\n"
                "3. Try doing the work yourself with direct tool calls\n"
                "4. If a reviewer was stuck, run tests manually with Bash"
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

        max_wait = RATE_LIMIT_MAX_WAIT_SEC
        if resets_at and 0 < wait_sec <= max_wait:
            wait_min = int(wait_sec / 60)
            log.info("Rate limited. Waiting %dm for reset...", wait_min)
            await db.update_run_status(run_id, "rate_limited")
            await db.save_rate_limit_reset(run_id, int(resets_at))
            await db.log_audit(run_id, "rate_limit_waiting", {
                "resets_at": resets_at, "wait_seconds": int(wait_sec),
            })
            # Poll in 10s intervals so stop/inject events aren't blocked
            remaining = wait_sec + RATE_LIMIT_SLEEP_BUFFER_SEC
            while remaining > 0:
                await asyncio.sleep(min(remaining, 10))
                remaining -= 10
                event = await self._events.drain()
                if event and event["event"] == "stop":
                    return "rate_limited"
            await db.update_run_status(run_id, "running")
            log.info("Rate limit reset, resuming")
            return None

        log.info("Rate limited. Resets in %dm (too long to wait).", int(wait_sec / 60))
        await db.update_run_status(run_id, "rate_limited")
        if resets_at:
            await db.save_rate_limit_reset(run_id, int(resets_at))
        await db.log_audit(run_id, "rate_limit_paused", {
            "resets_at": resets_at, "wait_seconds": int(wait_sec) if resets_at else None,
        })
        return "rate_limited"
