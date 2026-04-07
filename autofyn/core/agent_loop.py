"""Agent loop: session lifecycle management.

AgentLoop starts a Claude SDK session in the sandbox, delegates event
processing to StreamProcessor, and cleans up when done. The orchestrator
handles its own rounds internally (plan → build → review → commit → push).
"""

import asyncio
import logging
import os

from utils import db
from utils.models import RunContext
from utils.prompts import PromptLoader
from sandbox_manager.client import SandboxClient
from core.control import ControlHandler
from core.event_bus import EventBus
from core.stream import StreamProcessor
from tools.subagent_tracker import SubagentTracker
from tools.session import SessionGate

log = logging.getLogger("core.loop")


class AgentLoop:
    """Manages session lifecycle: start, stream, cleanup.

    Public API:
        execute(session_options, run_context, session, events, tracker,
                initial_prompt) -> str
    """

    def __init__(
        self, sandbox: SandboxClient, prompts: PromptLoader,
    ) -> None:
        self._sandbox = sandbox
        self._prompts = prompts

    async def execute(
        self, session_options: dict, run_context: RunContext,
        session: SessionGate, events: EventBus, tracker: SubagentTracker,
        initial_prompt: str,
    ) -> str:
        """Run the agent session. Returns final status string."""
        rid = run_context.run_id[:8]
        model = session_options.get("model", os.environ.get("AGENT_MODEL", "opus"))
        fallback_model = session_options.get("fallback_model")
        sandbox_session_id: str | None = None

        try:
            sandbox_session_id = await self._start_session(
                session_options, initial_prompt,
            )

            control = ControlHandler(
                self._sandbox, sandbox_session_id, run_context.run_id,
                events, session, self._prompts, model, fallback_model,
            )
            stream = StreamProcessor(
                self._sandbox, sandbox_session_id,
                run_context, session, tracker, control, events,
            )

            log.info("[%s] Session started | Duration: %s",
                     rid, session.time_remaining_str())

            while True:
                result = await stream.process()
                if result.should_stop:
                    return result.final_status or "stopped"
                if result.session_ended:
                    return "stopped" if control.stop_requested else "completed"
                log.info("[%s] Stream broke, re-entering", rid)

        except asyncio.CancelledError:
            await db.log_audit(run_context.run_id, "killed", {
                "elapsed_minutes": round(session.elapsed_minutes(), 1),
            })
            return "killed"
        except Exception as e:
            log.error("[%s] Fatal error: %s", rid, e, exc_info=True)
            await db.log_audit(run_context.run_id, "fatal_error", {
                "error": str(e),
            })
            return "error"
        finally:
            events.stop_pulse_checker()
            await self._cleanup_session(sandbox_session_id)

    async def _start_session(
        self, session_options: dict, initial_prompt: str,
    ) -> str:
        """Start a sandbox SDK session. Returns session_id."""
        session_options["initial_prompt"] = initial_prompt
        return await self._sandbox.start_session(session_options)

    async def _cleanup_session(self, sandbox_session_id: str | None) -> None:
        """Stop the sandbox session if one was started."""
        if sandbox_session_id is None:
            return
        try:
            await self._sandbox.stop_session(sandbox_session_id)
        except Exception as e:
            log.warning("Failed to stop sandbox session: %s", e)
