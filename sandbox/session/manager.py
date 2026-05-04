"""SessionManager — registry for Claude SDK sessions.

Thin coordinator that creates, looks up, and tears down Session instances.
The actual SDK lifecycle lives in session.session.Session.

Sessions stay readable after the SDK task finishes so the agent can drain
remaining events. The agent calls delete() to release the session and its
event log after draining.
"""

import asyncio
import logging
import uuid

from constants import MAX_CONCURRENT_SESSIONS
from session.errors import ClientNotReadyError
from session.errors import SessionNotFoundError
from session.event_log import SessionEventLog
from session.session import Session

log = logging.getLogger("sandbox.session_manager")


class SessionManager:
    """Manages Claude SDK sessions (active and finished-but-readable)."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def active_count(self) -> int:
        """Return the number of sessions with a running task (for concurrency limit)."""
        return sum(1 for s in self._sessions.values() if not s.finished)

    async def start(self, options_dict: dict) -> str:
        """Start a new Claude SDK session. Returns session_id."""
        if self.active_count() >= MAX_CONCURRENT_SESSIONS:
            raise RuntimeError(f"Max sessions ({MAX_CONCURRENT_SESSIONS}) reached")
        session_id = uuid.uuid4().hex[:12]
        session = Session(session_id, options_dict)
        self._sessions[session_id] = session
        session.task = asyncio.create_task(session.run())

        def _on_task_done(task: asyncio.Task) -> None:
            session.finished = True
            if not task.cancelled():
                exc = task.exception()
                if exc is not None:
                    log.warning(
                        "Session %s task raised an exception", session_id, exc_info=exc
                    )
            log.info("Session %s task completed (event log retained for draining)", session_id)

        session.task.add_done_callback(_on_task_done)
        log.info("Session %s started", session_id)
        return session_id

    def get_event_log(self, session_id: str) -> SessionEventLog:
        """Get the event log for SSE streaming."""
        return self._get(session_id).event_log

    async def send_message(self, session_id: str, text: str) -> None:
        """Send a follow-up query to the session."""
        s = self._get(session_id)
        if s.client is None:
            raise ClientNotReadyError(session_id)
        await s.client.query(text)

    async def interrupt(self, session_id: str) -> None:
        """Interrupt the current response."""
        s = self._get(session_id)
        if s.client is None:
            raise ClientNotReadyError(session_id)
        await s.client.interrupt()

    async def stop(self, session_id: str) -> None:
        """Stop a session's task. Session stays in registry for event draining."""
        session = self._sessions.get(session_id)
        if session and session.task and not session.finished:
            task = session.task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("Session %s raised exception during cancellation", session_id)
                raise

    def delete(self, session_id: str) -> None:
        """Remove a session and release its event log. Called by agent after draining."""
        self._sessions.pop(session_id, None)
        log.info("Session %s deleted", session_id)

    def unlock(self, session_id: str) -> None:
        """Force-unlock a session's time gate."""
        self._get(session_id).unlocked = True

    async def stop_all(self) -> None:
        """Stop all sessions and release them.

        Best-effort: one bad session must not prevent cleanup of the rest.
        """
        for sid in list(self._sessions.keys()):
            try:
                await self.stop(sid)
            except Exception:
                log.exception("Failed to stop session %s during stop_all", sid)
            self.delete(sid)

    def _get(self, session_id: str) -> Session:
        """Look up a session by ID."""
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        return session
