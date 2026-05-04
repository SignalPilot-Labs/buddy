"""Tests for SessionEventLog — the sequenced event log that replaced asyncio.Queue.

Verifies: append, overflow, read_after, trim_through, gap detection.
"""

import asyncio

import pytest

from session.event_log import (
    SessionEventLog,
    SessionEventLogOverflow,
    SessionEventGap,
)


class TestSessionEventLog:
    """Verify SessionEventLog correctness."""

    def test_append_and_read(self) -> None:
        """Events are appended with monotonic seq numbers."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("tool_use", {"tool": "Edit"})
        log.append("tool_done", {"tool": "Edit"})

        assert log.latest_seq == 2

    @pytest.mark.asyncio
    async def test_read_after_returns_events(self) -> None:
        """read_after returns events with seq > after_seq."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("a", {"i": 1})
        log.append("b", {"i": 2})
        log.append("c", {"i": 3})

        events = await log.read_after(1)
        assert len(events) == 2
        assert events[0].seq == 2
        assert events[1].seq == 3

    @pytest.mark.asyncio
    async def test_read_after_zero_returns_all(self) -> None:
        """read_after(0) returns all events."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("a", {})
        log.append("b", {})

        events = await log.read_after(0)
        assert len(events) == 2

    def test_overflow_fails_loudly(self) -> None:
        """Exceeding max_bytes raises SessionEventLogOverflow."""
        log = SessionEventLog(max_bytes=50)
        log.append("small", {"x": 1})

        with pytest.raises(SessionEventLogOverflow):
            log.append("big", {"data": "x" * 100})

    def test_overflow_marks_failed(self) -> None:
        """After overflow, further appends also raise."""
        log = SessionEventLog(max_bytes=50)
        log.append("small", {"x": 1})

        with pytest.raises(SessionEventLogOverflow):
            log.append("big", {"data": "x" * 100})

        with pytest.raises(SessionEventLogOverflow):
            log.append("another", {})

    @pytest.mark.asyncio
    async def test_overflow_event_is_readable(self) -> None:
        """The overflow event itself is appended with a seq and readable."""
        log = SessionEventLog(max_bytes=50)
        log.append("small", {"x": 1})

        with pytest.raises(SessionEventLogOverflow):
            log.append("big", {"data": "x" * 100})

        events = await log.read_after(1)
        assert len(events) == 1
        assert events[0].event == "session_event_log_overflow"
        assert events[0].seq == 2

    def test_trim_through_removes_events(self) -> None:
        """trim_through discards events and frees bytes."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("a", {"i": 1})
        log.append("b", {"i": 2})
        log.append("c", {"i": 3})

        log.trim_through(2)
        assert len(log._events) == 1
        assert log._events[0].seq == 3
        assert log._low_water_mark == 2

    def test_trim_through_frees_bytes(self) -> None:
        """Total bytes decrease after trimming."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("a", {"data": "x" * 100})
        bytes_before = log._total_bytes

        log.trim_through(1)
        assert log._total_bytes < bytes_before

    @pytest.mark.asyncio
    async def test_gap_detection(self) -> None:
        """read_after raises SessionEventGap if after_seq < low_water_mark."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("a", {})
        log.append("b", {})
        log.append("c", {})

        log.trim_through(2)

        with pytest.raises(SessionEventGap):
            await log.read_after(0)

    @pytest.mark.asyncio
    async def test_read_after_at_low_water_mark_works(self) -> None:
        """read_after(low_water_mark) is valid — returns events after the mark."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("a", {})
        log.append("b", {})
        log.append("c", {})

        log.trim_through(2)

        events = await log.read_after(2)
        assert len(events) == 1
        assert events[0].seq == 3

    @pytest.mark.asyncio
    async def test_read_after_waits_for_new_events(self) -> None:
        """read_after blocks until a new event is appended."""
        log = SessionEventLog(max_bytes=10_000)
        log.append("a", {})

        async def _delayed_append() -> None:
            await asyncio.sleep(0.01)
            log.append("b", {"delayed": True})

        task = asyncio.create_task(_delayed_append())
        events = await log.read_after(1)
        await task

        assert len(events) == 1
        assert events[0].data["delayed"] is True

    def test_seq_included_in_append_return(self) -> None:
        """append returns the assigned seq."""
        log = SessionEventLog(max_bytes=10_000)
        seq1 = log.append("a", {})
        seq2 = log.append("b", {})

        assert seq1 == 1
        assert seq2 == 2
