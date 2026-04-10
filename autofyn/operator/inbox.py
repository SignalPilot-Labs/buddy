"""OperatorInbox — run-scoped queue of operator events and pending messages.

One OperatorInbox per run. Lives longer than any single round: if the
operator injects a message mid-round-3 and the round ends before it can
be delivered, the inbox carries it into round 4's initial prompt.

The HTTP endpoints push events; the round loop drains them. Events are
dataclasses defined in `utils.models` — this module is behavior only.
"""

import asyncio
import logging

from utils.models import EventKind, OperatorEvent

log = logging.getLogger("operator.inbox")


class OperatorInbox:
    """Run-scoped queue of operator events + undelivered inject messages.

    Public API:
        push(kind, payload)           — called from HTTP handlers
        next_event()                  — async, blocks until an event arrives
        try_next_event()              — non-blocking peek
        queue_message(text)           — remember an inject for later delivery
        take_pending_messages()       — drain and clear queued messages
        peek_pending_messages()       — read without clearing
        has_stop()                    — has a stop been requested
        mark_stopped()                — record that stop was requested
        wait_for_resume_or_stop()     — used when a round ends in pause
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[OperatorEvent] = asyncio.Queue()
        self._pending_messages: list[str] = []
        self._stop_requested: bool = False

    # ── Ingress (HTTP handlers) ────────────────────────────────────────

    def push(self, kind: EventKind, payload: str) -> None:
        """Enqueue an operator event. Non-blocking."""
        self._queue.put_nowait(OperatorEvent(kind=kind, payload=payload))

    # ── Egress (round loop + session runner) ───────────────────────────

    async def next_event(self) -> OperatorEvent:
        """Block until the next operator event arrives."""
        return await self._queue.get()

    def try_next_event(self) -> OperatorEvent | None:
        """Return the next event without blocking, or None if the queue is empty."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def wait_for_resume_or_stop(self) -> OperatorEvent:
        """Block until a resume or stop event arrives (discarding other events).

        Inject events received during a pause are queued as pending messages
        so they are delivered at the start of the next round.
        """
        while True:
            event = await self._queue.get()
            if event.kind in ("resume", "stop"):
                if event.kind == "stop":
                    self._stop_requested = True
                return event
            if event.kind == "inject":
                self._pending_messages.append(event.payload)
                continue
            log.debug("Ignoring %s event while paused", event.kind)

    # ── Pending inject messages ────────────────────────────────────────

    def queue_message(self, text: str) -> None:
        """Buffer an inject message for later delivery."""
        self._pending_messages.append(text)

    def take_pending_messages(self) -> list[str]:
        """Return and clear all buffered inject messages."""
        messages = list(self._pending_messages)
        self._pending_messages.clear()
        return messages

    def peek_pending_messages(self) -> list[str]:
        """Return a copy of buffered messages without clearing them."""
        return list(self._pending_messages)

    # ── Stop flag ──────────────────────────────────────────────────────

    def has_stop(self) -> bool:
        """True once a stop event has been observed."""
        return self._stop_requested

    def mark_stopped(self) -> None:
        """Record that a stop has been requested (without enqueueing one)."""
        self._stop_requested = True
