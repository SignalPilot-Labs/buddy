"""Event delivery between HTTP handlers and the agent loop.

EventBus owns the asyncio.Queue, pause handler, and stuck-subagent
pulse checker. All state lives on the instance.
"""

import asyncio
import json
import logging

from utils import db
from utils.constants import PULSE_CHECK_INTERVAL_SEC
from tools.subagent_tracker import SubagentTracker

log = logging.getLogger("core.events")


class EventBus:
    """Delivers control events from HTTP endpoints to the agent loop.

    Public API:
        push(event, payload)    — called by server HTTP handlers
        drain() -> dict | None  — non-blocking check, called mid-round
        handle_pause(run_id)    — blocking wait for resume/stop/inject
        start_pulse_checker()   — background stuck-subagent detection
        stop_pulse_checker()    — cancel the background task
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._pulse_task: asyncio.Task | None = None

    def push(self, event: str, payload: str | None) -> None:
        """Push an event into the queue."""
        self._queue.put_nowait({"event": event, "payload": payload})

    async def drain(self) -> dict | None:
        """Non-blocking: return the next event or None."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def wait_for_event(self) -> dict:
        """Block until an event arrives. Cancellation-safe."""
        return await self._queue.get()

    async def handle_pause(self, run_id: str) -> str:
        """Block until resume/stop/inject event arrives. Returns action string."""
        log.info("PAUSED — waiting for event...")
        await db.update_run_status(run_id, "paused")

        while True:
            event = await self.wait_for_event()
            kind = event["event"]
            if kind == "resume":
                log.info("RESUMED")
                await db.update_run_status(run_id, "running")
                return "resume"
            if kind == "stop":
                log.info("STOPPED during pause")
                return "stop"
            if kind == "inject":
                payload = event.get("payload", "")
                log.info("INJECTED during pause: %s", payload[:100])
                await db.update_run_status(run_id, "running")
                return f"inject:{payload}"
            if kind == "unlock":
                return "unlock"
            log.warning("Unknown event during pause: %s", kind)

    def start_pulse_checker(self, run_id: str, tracker: SubagentTracker) -> None:
        """Start (or restart) the background stuck-subagent checker."""
        self.stop_pulse_checker()
        self._pulse_task = asyncio.create_task(self._pulse_loop(run_id, tracker))

    def stop_pulse_checker(self) -> None:
        """Cancel the background pulse checker."""
        if self._pulse_task and not self._pulse_task.done():
            self._pulse_task.cancel()
        self._pulse_task = None

    async def _pulse_loop(self, run_id: str, tracker: SubagentTracker) -> None:
        """Check for stuck subagents at a fixed interval."""
        while True:
            await asyncio.sleep(PULSE_CHECK_INTERVAL_SEC)
            stuck = tracker.get_stuck_subagents()
            if stuck:
                self.push("stuck_recovery", json.dumps(stuck))
                return
