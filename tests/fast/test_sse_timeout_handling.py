"""Regression test: handle_events catches asyncio.TimeoutError from read_after.

Bug: read_after() raises asyncio.TimeoutError when no events arrive within the
timeout window, but handle_events did not catch it, causing the SSE stream to
crash with an unhandled exception.

Fix: asyncio.TimeoutError is now caught in the inner try-except block and the
while loop continues, keeping the SSE connection alive during idle periods.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import sandbox.server as sandbox_server
from api.session import register as register_session
from sdk.event_log import SessionEventGap

_SESSION_ID = "abc123456789"
HTTP_200 = 200


def _build_app(event_log: MagicMock) -> web.Application:
    """Build minimal aiohttp app with session routes and a mocked event log."""
    app = web.Application(middlewares=[sandbox_server.error_middleware])

    sessions_mock = MagicMock()
    sessions_mock.get_event_log.return_value = event_log
    app["sessions"] = sessions_mock

    register_session(app)
    return app


class TestSSETimeoutHandling:
    """Regression: handle_events must not crash on asyncio.TimeoutError from read_after."""

    @pytest.mark.asyncio
    async def test_timeout_then_terminal_event_completes_stream(self) -> None:
        """TimeoutError on first read_after, then session_end — stream must complete cleanly."""
        event_log = MagicMock()

        call_count = 0

        async def _read_after_side_effect(after_seq: int, timeout: float) -> list:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError()
            # Second call returns a terminal event
            event = MagicMock()
            event.seq = 1
            event.event = "session_end"
            event.data = {"reason": "done"}
            return [event]

        event_log.read_after = _read_after_side_effect

        app = _build_app(event_log)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/session/{_SESSION_ID}/events",
                params={"after_seq": "0"},
            )
            assert resp.status == HTTP_200
            body = await resp.read()
            assert b"session_end" in body

        assert call_count == 2, "read_after should have been called twice (once per loop iteration)"

    @pytest.mark.asyncio
    async def test_timeout_does_not_raise_500(self) -> None:
        """TimeoutError from read_after must not propagate as a server error."""
        event_log = MagicMock()

        call_count = 0

        async def _read_after_side_effect(after_seq: int, timeout: float) -> list:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise asyncio.TimeoutError()
            # Third call returns a terminal event to end the stream
            event = MagicMock()
            event.seq = 1
            event.event = "session_end"
            event.data = {}
            return [event]

        event_log.read_after = _read_after_side_effect

        app = _build_app(event_log)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/session/{_SESSION_ID}/events",
                params={"after_seq": "0"},
            )
            # Stream response must be 200, not 500
            assert resp.status == HTTP_200

    @pytest.mark.asyncio
    async def test_event_gap_still_sends_error_event(self) -> None:
        """SessionEventGap must still send session_error and terminate — not be swallowed."""
        event_log = MagicMock()

        async def _read_after_raises_gap(after_seq: int, timeout: float) -> list:
            raise SessionEventGap(after_seq, after_seq + 10)

        event_log.read_after = _read_after_raises_gap

        app = _build_app(event_log)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get(
                f"/session/{_SESSION_ID}/events",
                params={"after_seq": "0"},
            )
            assert resp.status == HTTP_200
            body = await resp.read()
            assert b"session_error" in body
            assert b"session_event_gap" in body
