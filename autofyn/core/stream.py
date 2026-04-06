"""Stream processor: dispatches one round of SDK events from sandbox SSE.

StreamProcessor reads events from the sandbox's SSE stream instead of
a local SDK client. It handles assistant messages, tool calls, rate limits,
and result messages — same logic, different transport.
"""

import asyncio
import json
import logging
import time

from utils import db
from utils.constants import (
    LOG_PREVIEW_LIMIT,
    RATE_LIMIT_MAX_WAIT_SEC,
    RATE_LIMIT_SLEEP_BUFFER_SEC,
    TEXT_CHUNK_LIMIT,
)
from utils.models import RoundResult, RunContext
from utils.prompts import PromptLoader
from sandbox_manager.client import SandboxClient
from core.event_bus import EventBus
from tools.session import SessionGate
from tools.subagent_tracker import SubagentTracker

log = logging.getLogger("core.stream")


class StreamProcessor:
    """Processes one round of SDK events from sandbox SSE. Returns a RoundResult.

    Public API:
        process(round_num, is_planning) -> RoundResult
    """

    def __init__(
        self, sandbox: SandboxClient, session_id: str,
        run_context: RunContext, session: SessionGate,
        tracker: SubagentTracker,
        events: EventBus, prompts: PromptLoader,
        model: str, fallback_model: str | None,
    ) -> None:
        self._sandbox = sandbox
        self._session_id = session_id
        self._run_context = run_context
        self._session = session
        self._tracker = tracker
        self._events = events
        self._prompts = prompts
        self._model = model
        self._fallback_model = fallback_model

    async def process(self, round_num: int, is_planning: bool) -> RoundResult:
        """Process one round of sandbox SSE events."""
        tools: list[str] = []
        chunks: list[str] = []
        result_msg: dict | None = None
        should_stop = False
        final_status: str | None = None
        inject_payloads: list[str] = []

        async for event in self._sandbox.stream_events(self._session_id):
            action = await self._check_event(is_planning)
            if action == "stop":
                should_stop = True
                final_status = "stopped"
                break
            if action == "break":
                break
            if action and action.startswith("inject:"):
                inject_payloads.append(action[7:])

            event_type = event.get("event", "")
            data = event.get("data", {})

            if event_type == "assistant_message":
                self._collect_content(data, tools, chunks, is_planning)
                self._accumulate_usage(data)

            elif event_type == "rate_limit" and not is_planning:
                status = await self._handle_rate_limit(data)
                if status:
                    should_stop = True
                    final_status = status
                    break

            elif event_type == "result":
                result_msg = data
                await self._handle_result(data, round_num)

            elif event_type == "subagent_start":
                agent_id = data.get("agent_id", "")
                agent_type = data.get("agent_type", "")
                if agent_id:
                    self._tracker.track_subagent_start(agent_id, agent_type)

            elif event_type == "subagent_stop":
                agent_id = data.get("agent_id", "")
                if agent_id:
                    self._tracker.track_subagent_stop(agent_id)

            elif event_type == "tool_use":
                agent_id = data.get("agent_id")
                if agent_id:
                    self._tracker.track_tool_use(agent_id)

            elif event_type == "end_session":
                self._session.mark_ended()

            elif event_type == "end_session_denied":
                log.info("end_session denied: %s", data.get("reason", "unknown"))

            elif event_type in ("session_end", "session_error"):
                if event_type == "session_error":
                    log.error("Session error: %s", data.get("error", "unknown"))
                break

        return RoundResult(
            should_stop=should_stop, final_status=final_status,
            session_ended=self._session.has_ended(),
            result_message=result_msg,
            round_tools=tools, round_text_chunks=chunks,
            pending_injects=inject_payloads,
        )

    # ── Event Handling ──

    async def _check_event(self, is_planning: bool) -> str | None:
        """Check for mid-round control events. Returns action or None."""
        event = await self._events.drain()
        if not event:
            return None

        kind = event["event"]
        run_id = self._run_context.run_id

        if kind == "stop":
            log.info("INSTANT STOP")
            await self._sandbox.interrupt_session(self._session_id)
            await db.log_audit(run_id, "stop_requested", {
                "reason": event.get("payload", "Operator stop"), "instant": True,
            })
            return "stop"

        if kind == "pause" and not is_planning:
            await self._sandbox.interrupt_session(self._session_id)
            result = await self._events.handle_pause(run_id)
            if result == "stop":
                return "stop"
            if result == "resume":
                await self._sandbox.send_message(
                    self._session_id, self._prompts.build_continuation_prompt(),
                )
                return "break"
            if result.startswith("inject:"):
                return f"inject:{result[7:]}"
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
            await self._sandbox.interrupt_session(self._session_id)

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
            await self._sandbox.send_message(self._session_id, recovery)
            return "break"

        return None

    # ── Message Handlers ──

    def _collect_content(
        self, data: dict, tools: list[str], chunks: list[str], is_planning: bool,
    ) -> None:
        """Extract text chunks and tool names from assistant message data."""
        tag = "[PLANNER] " if is_planning else ""
        for block in data.get("content", []):
            block_type = block.get("type", "")
            if block_type == "text":
                text = block.get("text", "")
                log.info("%s%s", tag, text[:LOG_PREVIEW_LIMIT].replace("\n", " "))
                chunks.append(text[:TEXT_CHUNK_LIMIT])
            elif block_type == "thinking":
                log.info("%s[thinking] %s...", tag, block.get("thinking", "")[:100])
            elif block_type == "tool_use":
                log.info("Tool: %s", block.get("name", ""))
                tools.append(block.get("name", ""))

    def _accumulate_usage(self, data: dict) -> None:
        """Add usage to run context."""
        usage = data.get("usage")
        if usage:
            self._run_context.total_input_tokens += usage.get("input_tokens", 0)
            self._run_context.total_output_tokens += usage.get("output_tokens", 0)

    async def _handle_result(self, data: dict, round_num: int) -> None:
        """Save session ID, update costs, log round."""
        session_id = data.get("session_id")
        if session_id:
            await db.save_session_id(self._run_context.run_id, session_id)
        cost = data.get("total_cost_usd")
        if cost:
            self._run_context.total_cost = cost
        usage = data.get("usage")
        if usage:
            self._run_context.total_input_tokens = usage.get("input_tokens", self._run_context.total_input_tokens)
            self._run_context.total_output_tokens = usage.get("output_tokens", self._run_context.total_output_tokens)
        await db.log_audit(self._run_context.run_id, "round_complete", {
            "round": round_num + 1, "turns": data.get("num_turns"),
            "cost_usd": cost,
            "elapsed_minutes": round(self._session.elapsed_minutes(), 1),
        })

    async def _handle_rate_limit(self, data: dict) -> str | None:
        """Handle rate limit. Returns final_status if should stop."""
        run_id = self._run_context.run_id
        await db.log_audit(run_id, "rate_limit", {
            "status": data.get("status"), "resets_at": data.get("resets_at"),
            "utilization": data.get("utilization"),
        })
        if data.get("status") != "rejected":
            return None

        resets_at = data.get("resets_at")
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
