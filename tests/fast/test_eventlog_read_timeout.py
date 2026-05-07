"""Regression test: SessionEventLog.read_after() must not block indefinitely.

Before the fix, read_after() awaited self._notify.wait() with no timeout,
causing consumers to hang forever when no events are ever appended.
After the fix, read_after() wraps the wait in asyncio.wait_for() and raises
asyncio.TimeoutError when timeout expires.
"""

import asyncio

import pytest

from sdk.event_log import SessionEventLog


class TestEventLogReadTimeout:
    """Verify read_after raises TimeoutError instead of blocking indefinitely."""

    @pytest.mark.asyncio
    async def test_read_after_raises_timeout_when_no_events(self) -> None:
        """read_after raises asyncio.TimeoutError when no events appear within timeout."""
        log = SessionEventLog(max_bytes=10_000)

        with pytest.raises(asyncio.TimeoutError):
            await log.read_after(0, 0.1)

    @pytest.mark.asyncio
    async def test_read_after_completes_within_deadline(self) -> None:
        """Task calling read_after completes within ~0.2s when timeout=0.1."""
        log = SessionEventLog(max_bytes=10_000)

        task = asyncio.create_task(log.read_after(0, 0.1))
        done, pending = await asyncio.wait({task}, timeout=0.2)

        assert task in done, "read_after did not complete within 0.2s"
        assert len(pending) == 0

        with pytest.raises(asyncio.TimeoutError):
            task.result()

    @pytest.mark.asyncio
    async def test_read_after_returns_events_before_timeout(self) -> None:
        """read_after returns events appended before the timeout expires."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("test_event", {"value": 42})

        events = await log.read_after(0, 0.1)

        assert len(events) == 1
        assert events[0].event == "test_event"
        assert events[0].data["value"] == 42

    @pytest.mark.asyncio
    async def test_read_after_waits_and_returns_late_event(self) -> None:
        """read_after returns an event appended after a brief delay (within timeout)."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("first", {})

        async def _append_later() -> None:
            await asyncio.sleep(0.05)
            log.append("second", {"late": True})

        task = asyncio.create_task(_append_later())
        events = await log.read_after(1, 1.0)
        await task

        assert len(events) == 1
        assert events[0].event == "second"
        assert events[0].data["late"] is True
