"""Session runner: owns the asyncio.wait event loop and session lifecycle.

Races the sandbox SSE stream against control events for zero-latency
stop/pause. Delegates SSE dispatch to SSEDispatcher and control handling
to ControlHandler — neither knows about the event loop.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator

from utils import db
from utils.constants import SESSION_IDLE_TIMEOUT_SEC
from utils.models import RunContext, StreamResult
from utils.prompts import PromptLoader
from sandbox_manager.client import SandboxClient
from core.control import ControlHandler
from core.event_bus import EventBus
from core.sse_dispatch import SSEDispatcher
from tools.session import SessionGate
from tools.subagent_tracker import SubagentTracker

log = logging.getLogger("core.runner")


class SessionRunner:
    """Manages sandbox session lifecycle and the event processing loop.

    Public API:
        execute(session_options, run_context, session, events, tracker,
                initial_prompt) -> str (final status)
    """

    def __init__(
        self,
        sandbox: SandboxClient,
        prompts: PromptLoader,
    ) -> None:
        self._sandbox = sandbox
        self._prompts = prompts

    async def execute(
        self,
        session_options: dict,
        run_context: RunContext,
        session: SessionGate,
        events: EventBus,
        tracker: SubagentTracker,
        initial_prompt: str,
    ) -> str:
        """Start a session, process events, clean up. Returns final status."""
        rid = run_context.run_id[:8]
        model = session_options.get("model", os.environ.get("AGENT_MODEL", "opus"))
        fallback_model = session_options.get("fallback_model")
        session_id: str | None = None

        try:
            session_id = await self._start_session(session_options, initial_prompt)

            control = ControlHandler(
                self._sandbox, session_id, run_context.run_id,
                events, session, self._prompts, model, fallback_model,
            )
            dispatcher = SSEDispatcher(run_context, session, tracker)

            log.info("[%s] Session started | Duration: %s", rid, session.time_remaining_str())

            while True:
                result = await self._process_stream(
                    session_id, run_context, session, control, dispatcher, events,
                )
                if result.should_stop:
                    return result.final_status or "stopped"
                if result.session_ended:
                    return "stopped" if control.stop_requested else "completed"
                if result.pause:
                    action = await control.resolve_pause()
                    if action.stop:
                        return action.final_status or "stopped"
                log.info("[%s] Stream broke, re-entering", rid)

        except asyncio.CancelledError:
            await db.log_audit(run_context.run_id, "killed", {
                "elapsed_minutes": round(session.elapsed_minutes(), 1),
            })
            return "killed"
        except Exception as exc:
            log.error("[%s] Fatal error: %s", rid, exc, exc_info=True)
            await db.log_audit(run_context.run_id, "fatal_error", {"error": str(exc)})
            return "error"
        finally:
            events.stop_pulse_checker()
            await self._cleanup_session(session_id)

    async def _process_stream(
        self,
        session_id: str,
        run_context: RunContext,
        session: SessionGate,
        control: ControlHandler,
        dispatcher: SSEDispatcher,
        events: EventBus,
    ) -> StreamResult:
        """Race SSE stream against control events until one side stops."""
        result_msg: dict | None = None
        should_stop = False
        pause_requested = False
        final_status: str | None = None
        session_dead = False

        stream_iter: AsyncIterator[dict] = self._sandbox.stream_events(session_id).__aiter__()
        control_task = asyncio.create_task(events.wait_for_event())
        sse_task = asyncio.create_task(_next_sse(stream_iter))
        idle_task = asyncio.create_task(asyncio.sleep(SESSION_IDLE_TIMEOUT_SEC))

        try:
            while True:
                done, _ = await asyncio.wait(
                    {sse_task, control_task, idle_task}, return_when=asyncio.FIRST_COMPLETED,
                )

                if control_task in done:
                    action = await control.handle_event(control_task.result())
                    control_task = asyncio.create_task(events.wait_for_event())
                    if action.stop:
                        should_stop = True
                        final_status = action.final_status
                        break
                    if action.pause:
                        pause_requested = True
                        break
                    if action.break_stream:
                        break

                if sse_task in done:
                    sse_event = sse_task.result()
                    if sse_event is None:
                        break
                    sse_task = asyncio.create_task(_next_sse(stream_iter))
                    idle_task.cancel()
                    idle_task = asyncio.create_task(asyncio.sleep(SESSION_IDLE_TIMEOUT_SEC))

                    dispatched = await dispatcher.dispatch(sse_event)

                    if dispatched.result_data is not None:
                        result_msg = dispatched.result_data

                    if dispatched.rate_limit_data is not None:
                        action = await control.handle_rate_limit(
                            dispatched.rate_limit_data, run_context,
                        )
                        if action.stop:
                            should_stop = True
                            final_status = action.final_status
                            break

                    if dispatched.subagent_completed:
                        await control.on_subagent_complete(run_context)

                if idle_task in done:
                    log.info("[%s] Session idle for %ds — sending nudge",
                             run_context.run_id[:8], SESSION_IDLE_TIMEOUT_SEC)
                    await db.log_audit(run_context.run_id, "idle_nudge", {
                        "idle_seconds": SESSION_IDLE_TIMEOUT_SEC,
                    })
                    try:
                        await self._sandbox.send_message(session_id, self._prompts.build_idle_nudge(SESSION_IDLE_TIMEOUT_SEC))
                    except Exception:
                        log.warning("[%s] Idle nudge failed — session dead after stream break", run_context.run_id[:8])
                        await db.log_audit(run_context.run_id, "session_dead_after_stream_break", {})
                        session_dead = True
                        break
                    idle_task = asyncio.create_task(asyncio.sleep(SESSION_IDLE_TIMEOUT_SEC))

        finally:
            sse_task.cancel()
            control_task.cancel()
            idle_task.cancel()

        return StreamResult(
            should_stop=should_stop,
            final_status=final_status,
            session_ended=session.has_ended() or session_dead,
            result_message=result_msg,
            pause=pause_requested,
        )

    async def _start_session(self, session_options: dict, initial_prompt: str) -> str:
        """Start a sandbox SDK session. Returns session_id."""
        session_options["initial_prompt"] = initial_prompt
        return await self._sandbox.start_session(session_options)

    async def _cleanup_session(self, session_id: str | None) -> None:
        """Stop the sandbox session if one was started."""
        if session_id is None:
            return
        try:
            await self._sandbox.stop_session(session_id)
        except Exception as exc:
            log.warning("Failed to stop sandbox session: %s", exc)


async def _next_sse(stream_iter: AsyncIterator[dict]) -> dict | None:
    """Get next SSE event or None if stream is exhausted."""
    try:
        return await stream_iter.__anext__()
    except StopAsyncIteration:
        return None
