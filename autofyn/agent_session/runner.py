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
import logging
from collections.abc import AsyncGenerator

from prompts.loader import render_idle_nudge
from sandbox_client.client import SandboxClient
from sandbox_client.handlers.session import SessionNotReadyError
from user.control import UserControl
from user.inbox import UserInbox
from agent_session.pulse import PulseWatchdog
from agent_session.stream import StreamDispatcher, StreamSignal
from agent_session.time_lock import TimeLock
from agent_session.tracker import SubagentTracker
from db.constants import (
    RUN_STATUS_RATE_LIMITED,
    RUN_STATUS_RUNNING,
)
from utils import db
from utils.db_logging import log_audit
from utils.constants import idle_nudge_max_attempts
from utils.models import RoundResult, RunContext
from utils.run_config import RunAgentConfig

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
        run_config: RunAgentConfig,
    ) -> None:
        self._sandbox = sandbox
        self._run = run
        self._inbox = inbox
        self._time_lock = time_lock
        self._run_config = run_config
        self._rid = run.run_id[:8]

    async def run(
        self,
        options: dict,
        initial_prompt: str,
        round_number: int,
    ) -> RoundResult:
        """Start the sandbox session and run until the round ends."""
        session_id: str | None = None
        tracker = SubagentTracker(self._run_config)
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
            watchdog = PulseWatchdog(
                self._sandbox,
                self._run.run_id,
                self._rid,
                self._inbox,
                self._run_config,
            )
            pulse = asyncio.create_task(watchdog.run(tracker, session_id))
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
            await log_audit(
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
            await log_audit(
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
        stream_iter: AsyncGenerator[dict, None] = self._sandbox.session.stream_events(
            session_id,
        )

        sse_task = asyncio.create_task(_next_event(stream_iter))
        op_task = asyncio.create_task(self._inbox.next_event())
        idle_task: asyncio.Task[None] | None = asyncio.create_task(
            asyncio.sleep(self._run_config.session_idle_timeout_sec),
        )
        nudge_count = 0
        idle_since: float = asyncio.get_event_loop().time()
        is_rate_limited = False

        try:
            while True:
                wait_set: set[asyncio.Task] = {sse_task, op_task}
                if idle_task is not None:
                    wait_set.add(idle_task)

                done, _ = await asyncio.wait(
                    wait_set,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if op_task in done:
                    op_task, terminal = await self._handle_user_event(
                        op_task, control, session_id
                    )
                    if terminal is not None:
                        return terminal

                fired_idle = idle_task

                if sse_task in done:
                    sse_task, terminal, is_rate_limited = await self._handle_sse_event(
                        sse_task,
                        stream_iter,
                        dispatcher,
                        control,
                        session_id,
                        round_number,
                        is_rate_limited,
                    )
                    if terminal is not None:
                        return terminal
                    # Manage idle timer after SSE activity.
                    if idle_task is not None:
                        idle_task.cancel()
                    if (
                        dispatcher.has_tools_in_flight()
                        or dispatcher.has_active_subagents()
                        or is_rate_limited
                    ):
                        idle_task = None
                    else:
                        idle_task = asyncio.create_task(
                            asyncio.sleep(self._run_config.session_idle_timeout_sec),
                        )
                    nudge_count = 0
                    idle_since = asyncio.get_event_loop().time()

                if idle_task is not None and idle_task is fired_idle and fired_idle in done:
                    terminal, nudge_count, idle_task = await self._handle_idle_timeout(
                        round_number, nudge_count, idle_since, session_id
                    )
                    if terminal is not None:
                        return terminal
        finally:
            sse_task.cancel()
            op_task.cancel()
            if idle_task is not None:
                idle_task.cancel()
            # Wait for sse_task cancellation to complete before closing the
            # generator — aclose() on a running async generator raises
            # "asynchronous generator is already running".
            try:
                await sse_task
            except (asyncio.CancelledError, Exception):
                pass
            await stream_iter.aclose()

    async def _handle_user_event(
        self,
        op_task: asyncio.Task,
        control: UserControl,
        session_id: str,
    ) -> tuple[asyncio.Task, RoundResult | None]:
        """Process a user inbox event. Returns (new_op_task, terminal_result_or_none)."""
        event = op_task.result()
        op_task = asyncio.create_task(self._inbox.next_event())
        outcome = await control.handle(event)
        if outcome.kind == "break_stop":
            return op_task, RoundResult(status="stopped", session_id=session_id)
        if outcome.kind == "break_pause":
            return op_task, RoundResult(status="paused", session_id=session_id)
        return op_task, None

    async def _handle_sse_event(
        self,
        sse_task: asyncio.Task,
        stream_iter: AsyncGenerator[dict, None],
        dispatcher: StreamDispatcher,
        control: UserControl,
        session_id: str,
        round_number: int,
        is_rate_limited: bool,
    ) -> tuple[asyncio.Task, RoundResult | None, bool]:
        """Process one SSE event. Returns (new_sse_task, terminal_result_or_none, new_is_rate_limited)."""
        sse_event = sse_task.result()
        if sse_event is None:
            return sse_task, RoundResult(status="complete", session_id=session_id), is_rate_limited
        sse_task = asyncio.create_task(_next_event(stream_iter))
        signal = await dispatcher.dispatch(sse_event)
        terminal = await self._apply_signal(signal, session_id, control, round_number)
        if terminal is not None:
            return sse_task, terminal, is_rate_limited

        # Track rate limit state for idle suppression and DB status transitions.
        if signal.kind == "rate_limit_info":
            is_rate_limited = True
        elif is_rate_limited:
            is_rate_limited = False
            await db.update_run_status(self._run.run_id, RUN_STATUS_RUNNING)

        return sse_task, None, is_rate_limited

    async def _handle_idle_timeout(
        self,
        round_number: int,
        nudge_count: int,
        idle_since: float,
        session_id: str,
    ) -> tuple[RoundResult | None, int, asyncio.Task | None]:
        """Handle an idle timeout firing. Returns (terminal_result_or_none, new_nudge_count, new_idle_task)."""
        nudge_count += 1
        if nudge_count > idle_nudge_max_attempts():
            log.info(
                "[%s] Round %d idle after %d nudges — ending",
                self._rid,
                round_number,
                idle_nudge_max_attempts(),
            )
            await log_audit(
                self._run.run_id,
                "idle_timeout",
                {
                    "round_number": round_number,
                    "nudge_attempts": idle_nudge_max_attempts(),
                },
            )
            terminal = RoundResult(status="complete", session_id=session_id)
            return terminal, nudge_count, None

        backoff = self._run_config.session_idle_timeout_sec * (2 ** (nudge_count - 1))
        idle_seconds = int(asyncio.get_event_loop().time() - idle_since)
        log.info(
            "[%s] Round %d idle nudge %d/%d — next in %ds",
            self._rid,
            round_number,
            nudge_count,
            idle_nudge_max_attempts(),
            backoff,
        )
        await log_audit(
            self._run.run_id,
            "idle_nudge",
            {
                "round_number": round_number,
                "nudge_count": nudge_count,
                "idle_seconds": idle_seconds,
            },
        )
        try:
            await self._sandbox.session.interrupt(session_id)
        except SessionNotReadyError:
            log.debug("[%s] Skipping idle nudge — session client not ready", self._rid)
            idle_task = asyncio.create_task(asyncio.sleep(backoff))
            return None, nudge_count, idle_task
        self._inbox.push("inject", render_idle_nudge(idle_seconds))
        idle_task = asyncio.create_task(asyncio.sleep(backoff))
        return None, nudge_count, idle_task

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
                session_summary=signal.session_summary,
            )
        if signal.kind == "run_ended":
            return RoundResult(
                status="ended",
                session_id=session_id,
                round_summary=signal.round_summary,
                session_summary=signal.session_summary,
            )
        if signal.kind == "rate_limit_info":
            # Informational only — the SDK handles retry internally.
            # Log the event and update DB so the frontend can show a banner,
            # but do NOT end the round. The stream will resume automatically.
            data = signal.rate_limit_data or {}
            resets_at = data.get("resets_at")
            await log_audit(
                self._run.run_id,
                "rate_limit",
                {
                    "round_number": round_number,
                    "status": data.get("status"),
                    "resets_at": resets_at,
                    "utilization": data.get("utilization"),
                },
            )
            if resets_at:
                await db.save_rate_limit_reset(
                    self._run.run_id, int(resets_at),
                )
                await db.update_run_status(self._run.run_id, RUN_STATUS_RATE_LIMITED)
            return None  # continue the round
        if signal.kind == "session_error":
            return RoundResult(
                status="session_error",
                session_id=session_id,
                error=signal.error,
            )
        return None

    # ── Teardown ───────────────────────────────────────────────────────

    async def _safe_stop(self, session_id: str) -> None:
        """Best-effort stop; sandbox may already have torn down."""
        try:
            await self._sandbox.session.stop(session_id)
        except Exception as exc:
            log.warning("[%s] stop_session failed: %s", self._rid, exc, exc_info=True)


async def _next_event(stream_iter: AsyncGenerator[dict, None]) -> dict | None:
    """Pull one event or return None if the stream is exhausted."""
    try:
        return await stream_iter.__anext__()
    except StopAsyncIteration:
        return None
