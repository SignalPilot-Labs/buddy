"""Regression test: stream_events retries on 5xx HTTPStatusError, raises immediately on 4xx."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import httpx
import pytest

from sandbox_client.handlers.session import Session, SSE_RECONNECT_MAX_ATTEMPTS

HTTP_500 = 500
HTTP_503 = 503
HTTP_404 = 404
HTTP_200 = 200

_BASE_URL = "http://sandbox:8080"
_SESSION_ID = "sess-abc"


def _make_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Build an HTTPStatusError for the given status code."""
    request = httpx.Request("GET", f"{_BASE_URL}/session/{_SESSION_ID}/events")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


def _make_sse_chunk(seq: int) -> str:
    """Build a minimal SSE event string with a seq number."""
    data = json.dumps({"seq": seq, "type": "message", "text": "hello"})
    return f"event: message\ndata: {data}\n\n"


class _StreamContextManager:
    """Async context manager that simulates httpx streaming response."""

    def __init__(self, chunks: list[str], status_error: httpx.HTTPStatusError | None) -> None:
        self._chunks = chunks
        self._status_error = status_error

    async def __aenter__(self) -> "_StreamContextManager":
        if self._status_error is not None:
            raise self._status_error
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    def raise_for_status(self) -> None:
        pass

    async def aiter_text(self) -> AsyncIterator[str]:
        for chunk in self._chunks:
            yield chunk


def _make_stream_client(responses: list[_StreamContextManager]) -> MagicMock:
    """Build a mock httpx.AsyncClient whose .stream() cycles through the given responses."""
    call_count = 0

    @asynccontextmanager
    async def _fake_stream(*args: object, **kwargs: object) -> AsyncIterator[_StreamContextManager]:
        nonlocal call_count
        ctx = responses[call_count]
        call_count += 1
        async with ctx as c:
            yield c

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.stream = _fake_stream
    return mock_client


class TestSSEHttpStatusErrorRetry:
    """stream_events must retry on 5xx HTTPStatusError and raise immediately on 4xx."""

    @pytest.mark.asyncio
    async def test_5xx_retries_then_succeeds(self) -> None:
        """A single 500 followed by a successful stream should yield events from the second attempt."""
        responses = [
            _StreamContextManager([], _make_status_error(HTTP_500)),
            _StreamContextManager([_make_sse_chunk(1)], None),
        ]
        client = _make_stream_client(responses)
        session = Session(client)  # type: ignore[arg-type]

        events: list[dict] = []
        async for event in session.stream_events(_SESSION_ID, 0):
            events.append(event)

        assert len(events) == 1
        assert events[0]["data"]["seq"] == 1

    @pytest.mark.asyncio
    async def test_5xx_exhausts_retries_raises(self) -> None:
        """After SSE_RECONNECT_MAX_ATTEMPTS 500 errors, HTTPStatusError must propagate."""
        responses = [
            _StreamContextManager([], _make_status_error(HTTP_500))
            for _ in range(SSE_RECONNECT_MAX_ATTEMPTS)
        ]
        client = _make_stream_client(responses)
        session = Session(client)  # type: ignore[arg-type]

        with pytest.raises(httpx.HTTPStatusError):
            async for _ in session.stream_events(_SESSION_ID, 0):
                pass

    @pytest.mark.asyncio
    async def test_4xx_raises_immediately(self) -> None:
        """A 404 must raise HTTPStatusError immediately without retrying."""
        call_count = 0

        @asynccontextmanager
        async def _fake_stream(*args: object, **kwargs: object) -> AsyncIterator[_StreamContextManager]:
            nonlocal call_count
            call_count += 1
            raise _make_status_error(HTTP_404)
            yield  # type: ignore[misc]  # makes this an async generator

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.stream = _fake_stream

        session = Session(mock_client)  # type: ignore[arg-type]

        with pytest.raises(httpx.HTTPStatusError):
            async for _ in session.stream_events(_SESSION_ID, 0):
                pass

        assert call_count == 1, "4xx must not be retried"
