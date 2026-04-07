"""Tests for EventBus push/drain/wait_for_event."""

import asyncio

import pytest

from core.event_bus import EventBus


class TestEventBus:
    """Tests for EventBus push/drain/wait_for_event."""

    @pytest.mark.asyncio
    async def test_push_and_drain(self):
        bus = EventBus()
        bus.push("stop", "reason")
        event = await bus.drain()
        assert event is not None
        assert event["event"] == "stop"
        assert event["payload"] == "reason"

    @pytest.mark.asyncio
    async def test_drain_empty_returns_none(self):
        bus = EventBus()
        event = await bus.drain()
        assert event is None

    @pytest.mark.asyncio
    async def test_wait_for_event_receives_event(self):
        bus = EventBus()
        async def delayed_push():
            await asyncio.sleep(0.01)
            bus.push("inject", "hello")
        asyncio.create_task(delayed_push())
        event = await bus.wait_for_event()
        assert event["event"] == "inject"
        assert event["payload"] == "hello"

    @pytest.mark.asyncio
    async def test_wait_for_event_is_cancellable(self):
        bus = EventBus()
        task = asyncio.create_task(bus.wait_for_event())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_fifo_order(self):
        bus = EventBus()
        bus.push("first", None)
        bus.push("second", None)
        e1 = await bus.drain()
        e2 = await bus.drain()
        assert e1 is not None and e1["event"] == "first"
        assert e2 is not None and e2["event"] == "second"
