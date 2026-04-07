"""Operator control events and subagent boundary handling.

ControlHandler owns all communication between the dashboard/operator
and the orchestrator session. Two interception points:

1. Per-SSE-event: urgent control (stop, pause, unlock, stuck recovery)
2. Subagent boundary: time updates + pending user injects
"""

import asyncio
import json
import logging
import time

from utils import db
from utils.constants import (
    RATE_LIMIT_MAX_WAIT_SEC,
    RATE_LIMIT_SLEEP_BUFFER_SEC,
)
from utils.models import ControlAction, RunContext
from utils.prompts import PromptLoader
from sandbox_manager.client import SandboxClient
from core.event_bus import EventBus
from tools.session import SessionGate

log = logging.getLogger("core.control")


class ControlHandler:
    """Handles operator events, time updates, and rate limits.

    Public API:
        check_control_event() -> ControlAction
        on_subagent_complete(run_context) -> None
        handle_rate_limit(data, run_context) -> ControlAction
    """

    def __init__(
        self,
        sandbox: SandboxClient,
        session_id: str,
        run_id: str,
        events: EventBus,
        session: SessionGate,
        prompts: PromptLoader,
        model: str,
        fallback_model: str | None,
    ) -> None:
        self._sandbox = sandbox
        self._session_id = session_id
        self._run_id = run_id
        self._events = events
        self._session = session
        self._prompts = prompts
        self._model = model
        self._fallback_model = fallback_model
        self._rid = run_id[:8]
        self._pending_injects: list[str] = []
        self._stop_requested = False

    @property
    def stop_requested(self) -> bool:
        """Whether the operator has requested a stop."""
        return self._stop_requested

    # ── Urgent Control (per SSE event) ──

    async def check_control_event(self) -> ControlAction:
        """Non-blocking check for urgent control events."""
        event = await self._events.drain()
        if not event:
            return ControlAction.no_action()

        kind = event["event"]

        if kind == "stop":
            return await self._handle_stop(event)
        if kind == "pause":
            return await self._handle_pause()
        if kind == "unlock":
            return await self._handle_unlock()
        if kind == "stuck_recovery":
            return await self._handle_stuck_recovery(event)
        if kind == "inject":
            self._pending_injects.append(event.get("payload", ""))
        return ControlAction.no_action()

    async def _handle_stop(self, event: dict) -> ControlAction:
        """Interrupt current work, send stop prompt, break stream for re-entry."""
        log.info("[%s] STOP requested — interrupting and sending stop prompt", self._rid)
        reason = event.get("payload", "")
        await self._sandbox.interrupt_session(self._session_id)
        await self._sandbox.send_message(
            self._session_id, self._prompts.build_stop_prompt(reason),
        )
        await db.log_audit(self._run_id, "stop_requested", {
            "reason": reason or "Operator stop",
        })
        self._stop_requested = True
        return ControlAction(stop=False, break_stream=True, final_status=None)

    async def _handle_pause(self) -> ControlAction:
        """Interrupt session and wait for resume/stop/inject."""
        await self._sandbox.interrupt_session(self._session_id)
        result = await self._events.handle_pause(self._run_id)

        if result == "stop":
            return ControlAction(stop=True, break_stream=False, final_status="stopped")
        if result == "resume":
            await self._sandbox.send_message(
                self._session_id, self._prompts.build_continuation_prompt(),
            )
            return ControlAction(stop=False, break_stream=True, final_status=None)
        if result.startswith("inject:"):
            await self._sandbox.send_message(
                self._session_id, f"Operator message: {result[7:]}",
            )
            return ControlAction(stop=False, break_stream=True, final_status=None)
        if result == "unlock":
            return await self._handle_unlock()
        return ControlAction.no_action()

    async def _handle_unlock(self) -> ControlAction:
        """Force-unlock the session time lock."""
        self._session.force_unlock()
        await db.log_audit(self._run_id, "session_unlocked", {})
        return ControlAction.no_action()

    async def _handle_stuck_recovery(self, event: dict) -> ControlAction:
        """Interrupt session and send recovery instructions."""
        stuck_info = event.get("payload", "[]")
        log.info("[%s] STUCK RECOVERY: interrupting", self._rid)
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
        await db.log_audit(self._run_id, "stuck_recovery", {
            "stuck_info": stuck_info, "recovery_prompt": recovery,
        })
        await self._sandbox.send_message(self._session_id, recovery)
        return ControlAction(stop=False, break_stream=True, final_status=None)

    # ── Subagent Boundary ──

    async def on_subagent_complete(self, run_context: RunContext) -> None:
        """Deliver time update and pending user messages when a subagent finishes."""
        parts: list[str] = []

        duration = run_context.duration_minutes
        if duration > 0:
            elapsed = self._session.elapsed_minutes()
            remaining = self._session.time_remaining_str()
            pct = min(100, int((elapsed / duration) * 100))
            parts.append(f"⏱ {pct}% time used — {remaining} remaining.")

        for prompt in self._pending_injects:
            await db.log_audit(run_context.run_id, "prompt_injected", {
                "prompt": prompt, "delivery": "immediate",
            })
            parts.append(f"Operator message: {prompt}")
        self._pending_injects.clear()

        if parts:
            await self._sandbox.send_message(
                self._session_id, "\n\n".join(parts),
            )

    # ── Rate Limits ──

    async def handle_rate_limit(
        self, data: dict, run_context: RunContext,
    ) -> ControlAction:
        """Handle rate limit event. Returns action if should stop."""
        run_id = run_context.run_id
        await db.log_audit(run_id, "rate_limit", {
            "status": data.get("status"),
            "resets_at": data.get("resets_at"),
            "utilization": data.get("utilization"),
        })
        if data.get("status") != "rejected":
            return ControlAction.no_action()

        resets_at = data.get("resets_at")
        wait_sec = max(0, resets_at - time.time()) if resets_at else 0

        if self._fallback_model and self._fallback_model != self._model:
            log.info("[%s] Rate limited on %s, fallback to %s",
                     self._rid, self._model, self._fallback_model)
            await db.log_audit(run_id, "rate_limit_fallback", {
                "primary_model": self._model,
                "fallback_model": self._fallback_model,
            })
            return ControlAction.no_action()

        if resets_at and 0 < wait_sec <= RATE_LIMIT_MAX_WAIT_SEC:
            return await self._wait_for_rate_limit(
                run_id, wait_sec, resets_at,
            )

        log.info("[%s] Rate limited. Resets in %dm (too long).",
                 self._rid, int(wait_sec / 60))
        await db.update_run_status(run_id, "rate_limited")
        if resets_at:
            await db.save_rate_limit_reset(run_id, int(resets_at))
        await db.log_audit(run_id, "rate_limit_paused", {
            "resets_at": resets_at,
            "wait_seconds": int(wait_sec) if resets_at else None,
        })
        return ControlAction(stop=True, break_stream=False, final_status="rate_limited")

    async def _wait_for_rate_limit(
        self, run_id: str, wait_sec: float, resets_at: float,
    ) -> ControlAction:
        """Sleep until rate limit resets, checking for stop events."""
        log.info("[%s] Rate limited. Waiting %dm for reset...",
                 self._rid, int(wait_sec / 60))
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
                return ControlAction(stop=True, break_stream=False, final_status="rate_limited")
        await db.update_run_status(run_id, "running")
        log.info("[%s] Rate limit reset, resuming", self._rid)
        return ControlAction.no_action()

