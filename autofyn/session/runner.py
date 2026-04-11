"""RoundRunner — execute one orchestrator round against the sandbox.

The round loop in `lifecycle/round_loop.py` instantiates a RoundRunner
per round and calls `run()`. Each call owns exactly one Claude SDK
session in the sandbox. When it returns, the session is torn down and
the round loop decides whether to start another.

The runner races three async sources:

    1. Sandbox SSE stream — assistant messages, tool calls, results
    2. User inbox    — pause/stop/inject/unlock
    3. Idle timeout      — 2 min no-progress nudge

Event precedence: user events interrupt mid-stream; rate limits end
the round immediately so the outer loop can back off; ResultMessage
ends the round cleanly; stuck subagents are killed by a background
pulse task that pushes a synthetic stop event.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from sandbox_client.client import SandboxClient
from user.control import UserControl
from user.inbox import UserInbox
from session.stream import StreamDispatcher, StreamSignal
from session.time_lock import TimeLock
from session.tracker import SubagentTracker
from utils import db
from utils.constants import (
    PULSE_CHECK_INTERVAL_SEC,
    SESSION_IDLE_TIMEOUT_SEC,
)
from utils.models import RoundResult, RunContext

log = logging.getLogger("session.runner")


class RoundRunner:
    """Drive one orchestrator round from start to teardown.

    Public API:
        run(options, initial_prompt, round_number) -> RoundResult
    """

    def __init__(
        self,
        sandbox: SandboxClient,
        run: RunContext,
        inbox: UserInbox,
        time_lock: TimeLock,
    ) -> None:
        self._sandbox = sandbox
        self._run = run
        self._inbox = inbox
        self._time_lock = time_lock
        self._rid = run.run_id[:8]

    async def run(
        self,
        options: dict,
        initial_prompt: str,
        round_number: int,
    ) -> RoundResult:
        """Start the sandbox session and run until the round ends."""
        session_id: str | None = None
        tracker = SubagentTracker()
        dispatcher = StreamDispatcher(self._run, round_number, tracker)

        try:
            options["initial_prompt"] = initial_prompt
            session_id = await self._sandbox.session.start(options)
            log.info(
                "[%s] Round %d started (session %s)",
                self._rid,
                round_number,
                session_id,
            )
            control = UserControl(self._sandbox, session_id, self._inbox)
            pulse = asyncio.create_task(
                self._pulse_loop(tracker),
            )
            try:
                return await self._drive_stream(
                    session_id,
                    dispatcher,
                    control,
                    round_number,
                )
            finally:
                pulse.cancel()
        except asyncio.CancelledError:
            await db.log_audit(
                self._run.run_id,
                "killed",
                {
                    "elapsed_minutes": round(self._time_lock.elapsed_minutes(), 1),
                },
            )
            return RoundResult(status="stopped", session_id=session_id)
        except Exception as exc:
            log.error(
                "[%s] Round %d fatal error: %s",
                self._rid,
                round_number,
                exc,
                exc_info=True,
            )
            await db.log_audit(
                self._run.run_id,
                "fatal_error",
                {
                    "round_number": round_number,
                    "error": str(exc),
                },
            )
            return RoundResult(
                status="error",
                session_id=session_id,
                error=str(exc),
            )
        finally:
            if session_id:
                await self._safe_stop(session_id)

    # ── Core drive loop ────────────────────────────────────────────────

    async def _drive_stream(
        self,
        session_id: str,
        dispatcher: StreamDispatcher,
        control: UserControl,
        round_number: int,
    ) -> RoundResult:
        """Race SSE stream vs user inbox vs idle timeout until the round ends."""
        stream_iter: AsyncIterator[dict] = self._sandbox.session.stream_events(
            session_id,
        ).__aiter__()

        sse_task = asyncio.create_task(_next_event(stream_iter))
        op_task = asyncio.create_task(self._inbox.next_event())
        idle_task = asyncio.create_task(
            asyncio.sleep(SESSION_IDLE_TIMEOUT_SEC),
        )

        try:
            while True:
                done, _ = await asyncio.wait(
                    {sse_task, op_task, idle_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if op_task in done:
                    event = op_task.result()
                    op_task = asyncio.create_task(self._inbox.next_event())
                    outcome = await control.handle(event)
                    if outcome.kind == "break_stop":
                        return RoundResult(
                            status="stopped",
                            session_id=session_id,
                        )
                    if outcome.kind == "break_pause":
                        return RoundResult(
                            status="paused",
                            session_id=session_id,
                        )

                if sse_task in done:
                    sse_event = sse_task.result()
                    if sse_event is None:
                        return RoundResult(
                            status="complete",
                            session_id=session_id,
                        )
                    sse_task = asyncio.create_task(_next_event(stream_iter))
                    idle_task.cancel()
                    idle_task = asyncio.create_task(
                        asyncio.sleep(SESSION_IDLE_TIMEOUT_SEC),
                    )
                    signal = await dispatcher.dispatch(sse_event)
                    terminal = await self._apply_signal(
                        signal,
                        session_id,
                        control,
                        round_number,
                    )
                    if terminal is not None:
                        return terminal

                if idle_task in done:
                    log.info(
                        "[%s] Round %d idle %ds — ending round",
                        self._rid,
                        round_number,
                        SESSION_IDLE_TIMEOUT_SEC,
                    )
                    await db.log_audit(
                        self._run.run_id,
                        "idle_timeout",
                        {
                            "round_number": round_number,
                            "idle_seconds": SESSION_IDLE_TIMEOUT_SEC,
                        },
                    )
                    return RoundResult(
                        status="complete",
                        session_id=session_id,
                    )
        finally:
            sse_task.cancel()
            op_task.cancel()
            idle_task.cancel()

    async def _apply_signal(
        self,
        signal: StreamSignal,
        session_id: str,
        control: UserControl,
        round_number: int,
    ) -> RoundResult | None:
        """Apply a stream signal. Returns a RoundResult if the round should end."""
        if signal.kind == "continue":
            return None
        if signal.kind == "subagent_boundary":
            await control.flush_pending()
            return None
        if signal.kind == "round_complete":
            return RoundResult(
                status="complete",
                session_id=session_id,
                round_summary=signal.round_summary,
            )
        if signal.kind == "run_ended":
            return RoundResult(
                status="ended",
                session_id=session_id,
                round_summary=signal.round_summary,
            )
        if signal.kind == "rate_limited":
            data = signal.rate_limit_data or {}
            resets_at = data.get("resets_at")
            await db.log_audit(
                self._run.run_id,
                "rate_limit",
                {
                    "round_number": round_number,
                    "status": data.get("status"),
                    "resets_at": resets_at,
                    "utilization": data.get("utilization"),
                },
            )
            return RoundResult(
                status="rate_limited",
                session_id=session_id,
                rate_limit_resets_at=int(resets_at) if resets_at else None,
            )
        return None

    # ── Stuck-subagent pulse ───────────────────────────────────────────

    async def _pulse_loop(self, tracker: SubagentTracker) -> None:
        """Periodically push a synthetic stop if a subagent is stuck."""
        while True:
            await asyncio.sleep(PULSE_CHECK_INTERVAL_SEC)
            stuck = tracker.stuck_subagents()
            if not stuck:
                continue
            payload = json.dumps(
                [
                    {
                        "agent_id": s.agent_id,
                        "agent_type": s.agent_type,
                        "idle_seconds": s.idle_seconds,
                        "total_seconds": s.total_seconds,
                    }
                    for s in stuck
                ]
            )
            log.warning(
                "[%s] Stuck subagent(s) detected — stopping round: %s",
                self._rid,
                payload,
            )
            await db.log_audit(
                self._run.run_id,
                "stuck_recovery",
                {
                    "stuck": payload,
                },
            )
            self._inbox.push("stop", f"stuck subagents: {payload}")
            return

    # ── Teardown ───────────────────────────────────────────────────────

    async def _safe_stop(self, session_id: str) -> None:
        """Best-effort stop; sandbox may already have torn down."""
        try:
            await self._sandbox.session.stop(session_id)
        except Exception as exc:
            log.warning("[%s] stop_session failed: %s", self._rid, exc)


async def _next_event(stream_iter: AsyncIterator[dict]) -> dict | None:
    """Pull one event or return None if the stream is exhausted."""
    try:
        return await stream_iter.__anext__()
    except StopAsyncIteration:
        return None
