"""UserControl — apply user events to a running round.

The round's session runner races user events against the SSE stream.
When an event arrives, it calls `UserControl.handle()` to decide what
to do with the in-flight session.

Inject messages arriving mid-subagent are buffered on the inbox and
flushed at the next subagent boundary via `flush_pending()`.
"""

import logging

from sandbox_client.client import SandboxClient
from user.inbox import UserInbox
from utils.models import ControlOutcome, UserEvent

log = logging.getLogger("user.control")


class UserControl:
    """Applies user events to a running round's session.

    Public API:
        handle(event)           -> ControlOutcome
        flush_pending()         -> None     (call at subagent boundary)
        await_resume()          -> bool     (True=resume, False=stop)
    """

    def __init__(
        self,
        sandbox: SandboxClient,
        session_id: str,
        inbox: UserInbox,
    ) -> None:
        self._sandbox = sandbox
        self._session_id = session_id
        self._inbox = inbox

    # ── Event dispatch ─────────────────────────────────────────────────

    async def handle(self, event: UserEvent) -> ControlOutcome:
        """Route an user event and apply it to the running session."""
        if event.kind == "stop":
            return await self._handle_stop(event.payload)
        if event.kind == "pause":
            return await self._handle_pause()
        if event.kind == "inject":
            self._inbox.queue_message(event.payload)
            log.info("Queued user inject (%d chars)", len(event.payload))
            return ControlOutcome(kind="continue", reason="queued inject")
        if event.kind == "unlock":
            log.info("Unlock requested — forwarded to session gate")
            return ControlOutcome(kind="continue", reason="unlock forwarded")
        if event.kind == "resume":
            log.warning("Ignoring resume event outside of pause state")
            return ControlOutcome(kind="continue", reason="spurious resume")
        return ControlOutcome(kind="continue", reason="unknown event")

    # ── Subagent boundary ─────────────────────────────────────────────

    async def flush_pending(self) -> None:
        """Deliver all buffered inject messages to the session."""
        messages = self._inbox.take_pending_messages()
        if not messages:
            return
        for msg in messages:
            await self._sandbox.session.send_message(
                self._session_id,
                f"User message: {msg}",
            )

    # ── Pause blocking ─────────────────────────────────────────────────

    async def await_resume(self) -> bool:
        """Block until the user resumes or stops. Returns True on resume."""
        event = await self._inbox.wait_for_resume_or_stop()
        return event.kind == "resume"

    # ── Private ────────────────────────────────────────────────────────

    async def _handle_stop(self, reason: str) -> ControlOutcome:
        """Interrupt the session and signal the runner to tear down."""
        log.info("STOP requested: %s", reason or "user stop")
        await self._sandbox.session.interrupt(self._session_id)
        self._inbox.mark_stopped()
        return ControlOutcome(
            kind="break_stop",
            reason=reason or "user stop",
        )

    async def _handle_pause(self) -> ControlOutcome:
        """Interrupt the session and signal the runner to await resume."""
        log.info("PAUSE requested")
        await self._sandbox.session.interrupt(self._session_id)
        return ControlOutcome(kind="break_pause", reason="user pause")
