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
    OPERATOR_MESSAGES_PATH,
    RATE_LIMIT_MAX_WAIT_SEC,
    RATE_LIMIT_SLEEP_BUFFER_SEC,
)
from utils.models import ControlAction, ExecRequest, RunContext
from utils.shell import shell_quote
from utils.prompts import PromptLoader
from sandbox_manager.client import SandboxClient
from core.event_bus import EventBus
from tools.session import SessionGate

log = logging.getLogger("core.control")


class ControlHandler:
    """Handles operator events, time updates, and rate limits.

    Public API:
        handle_event(event) -> ControlAction
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

    # ── Urgent Control ──

    async def handle_event(self, event: dict) -> ControlAction:
        """Handle a control event delivered by the stream processor."""
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
        return ControlAction(stop=False, break_stream=True, final_status=None, pause=False)

    async def _handle_pause(self) -> ControlAction:
        """Interrupt session. If pending injects exist, deliver them instead of pausing."""
        await self._sandbox.interrupt_session(self._session_id)

        if self._pending_injects:
            await self._deliver_pending_injects()
            return ControlAction(stop=False, break_stream=True, final_status=None, pause=False)

        await db.log_audit(self._run_id, "pause_requested", {})
        return ControlAction(stop=False, break_stream=True, final_status=None, pause=True)

    async def resolve_pause(self) -> ControlAction:
        """Block until resume/stop/inject arrives. Called by SessionRunner after tasks are cancelled."""
        result = await self._events.handle_pause(self._run_id)

        if result == "stop":
            await db.log_audit(self._run_id, "stop_requested", {})
            return ControlAction(stop=True, break_stream=False, final_status="stopped", pause=False)
        if result == "resume":
            await db.log_audit(self._run_id, "resumed", {})
            await self._sandbox.send_message(
                self._session_id, self._prompts.build_continuation_prompt(),
            )
            return ControlAction(stop=False, break_stream=True, final_status=None, pause=False)
        if result.startswith("inject:"):
            prompt = result[7:]
            await db.log_audit(self._run_id, "resumed", {"via": "inject"})
            await db.log_audit(self._run_id, "prompt_injected", {
                "prompt": prompt, "delivery": "pause_resume",
            })
            await self._persist_operator_message(prompt)
            await self._sandbox.send_message(
                self._session_id, f"Operator message: {prompt}",
            )
            return ControlAction(stop=False, break_stream=True, final_status=None, pause=False)
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
        return ControlAction(stop=False, break_stream=True, final_status=None, pause=False)

    # ── Inject Delivery ──

    async def _persist_operator_message(self, prompt: str) -> None:
        """Append operator message to /tmp/operator-messages.md in the sandbox."""
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        line = f"[{ts}] {prompt}"
        try:
            await self._sandbox.exec(ExecRequest(
                args=["sh", "-c", f"mkdir -p /tmp && echo {shell_quote(line)} >> {OPERATOR_MESSAGES_PATH}"],
                cwd="/tmp",
                timeout=5,
                env={},
            ))
        except Exception as exc:
            log.warning("[%s] Failed to persist operator message: %s", self._rid, exc)

    async def _deliver_pending_injects(self) -> None:
        """Flush all pending injects into the session immediately."""
        for prompt in self._pending_injects:
            await db.log_audit(self._run_id, "prompt_injected", {
                "prompt": prompt, "delivery": "immediate",
            })
            await self._persist_operator_message(prompt)
            await self._sandbox.send_message(
                self._session_id, f"Operator message: {prompt}",
            )
        self._pending_injects.clear()

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
                "prompt": prompt, "delivery": "subagent_boundary",
            })
            await self._persist_operator_message(prompt)
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
        return ControlAction(stop=True, break_stream=False, final_status="rate_limited", pause=False)

    async def _wait_for_rate_limit(
        self, run_id: str, wait_sec: float, resets_at: float,
    ) -> ControlAction:
        """Sleep until rate limit resets or a stop event arrives (zero-latency).

        Non-stop events (pause, inject, unlock) are re-queued so they aren't
        lost while waiting for the rate limit to reset.
        """
        log.info("[%s] Rate limited. Waiting %dm for reset...",
                 self._rid, int(wait_sec / 60))
        await db.update_run_status(run_id, "rate_limited")
        await db.save_rate_limit_reset(run_id, int(resets_at))
        await db.log_audit(run_id, "rate_limit_waiting", {
            "resets_at": resets_at, "wait_seconds": int(wait_sec),
        })
        total_wait = wait_sec + RATE_LIMIT_SLEEP_BUFFER_SEC
        sleep_task = asyncio.create_task(asyncio.sleep(total_wait))
        control_task = asyncio.create_task(self._events.wait_for_event())
        try:
            while True:
                done, _ = await asyncio.wait(
                    {sleep_task, control_task}, return_when=asyncio.FIRST_COMPLETED,
                )
                if sleep_task in done:
                    break
                if control_task in done:
                    event = control_task.result()
                    if event["event"] == "stop":
                        return ControlAction(stop=True, break_stream=False, final_status="rate_limited", pause=False)
                    self._events.push(event["event"], event.get("payload"))
                    control_task = asyncio.create_task(self._events.wait_for_event())
        finally:
            sleep_task.cancel()
            control_task.cancel()
        await db.update_run_status(run_id, "running")
        log.info("[%s] Rate limit reset, resuming", self._rid)
        return ControlAction.no_action()

