"""Regression test: event_gen.aclose() is called on all paths in _execute_start.

Bug: The async generator from stream_start_events() was only closed on the
timeout exception path.  On the success path and on the early-return path
(process exits without AF_READY), aclose() was never called, leaving the
generator open and holding a reference to process.stdout.

Fix: Wrapped the _stream_and_collect call in try/finally so aclose() is
guaranteed regardless of success, early-return, or timeout.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.connector.server import ConnectorServer


TEST_SECRET = "test-secret"


def _make_server() -> ConnectorServer:
    """Build a ConnectorServer with mocked internals, no real aiohttp app."""
    with patch("cli.connector.server.web.Application"):
        srv = ConnectorServer.__new__(ConnectorServer)
        srv._secret = TEST_SECRET
        srv._port = 0
        srv._states = {}
        srv._heartbeat_tasks = {}
        srv._drain_tasks = {}
        srv._started_runs = {}
        srv._destroy_tasks = {}
        srv._app = None  # type: ignore[assignment]
    return srv


def _make_response() -> MagicMock:
    """Return a mock StreamResponse with async write()."""
    response = MagicMock()
    response.write = AsyncMock()
    return response


def _fake_process() -> MagicMock:
    """Return a minimal fake asyncio.subprocess.Process."""
    proc = MagicMock(spec=asyncio.subprocess.Process)
    proc.stdout = None
    return proc


class _TrackingAsyncGen:
    """Wraps an async generator to track whether aclose() was called."""

    def __init__(self, inner: AsyncGenerator[dict[str, Any], None]) -> None:
        self._inner = inner
        self.aclose_called = False

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        return self._inner.__aiter__()

    async def aclose(self) -> None:
        self.aclose_called = True
        await self._inner.aclose()


async def _gen_ready() -> AsyncGenerator[dict[str, Any], None]:
    """Yield a single AF_READY event then stop."""
    yield {
        "event": "ready",
        "host": "127.0.0.1",
        "port": 9999,
        "sandbox_secret": "sandbox-secret-abc",
    }


async def _gen_no_ready() -> AsyncGenerator[dict[str, Any], None]:
    """Yield only log events (no AF_READY) — simulates failed startup."""
    yield {"event": "log", "line": "starting..."}
    yield {"event": "log", "line": "exited"}


class TestEventGenAclose:
    """event_gen.aclose() must be called on success, early-return, and timeout paths."""

    @pytest.mark.asyncio
    async def test_aclose_called_on_success_path(self) -> None:
        """aclose() must be called when _stream_and_collect succeeds with AF_READY."""
        server = _make_server()
        process = _fake_process()
        response = _make_response()

        tracking_gen: _TrackingAsyncGen = _TrackingAsyncGen(_gen_ready())

        body: dict[str, Any] = {
            "run_key": "run-success",
            "ssh_target": "host",
            "sandbox_type": "docker",
            "start_cmd": "sandbox",
            "host_mounts": [],
            "work_dir": "",
        }

        async def _fake_stream_start_events(**kwargs: Any) -> tuple[asyncio.subprocess.Process, _TrackingAsyncGen]:
            return process, tracking_gen

        fake_state = MagicMock()
        fake_state.run_key = "run-success"

        with (
            patch("cli.connector.server.stream_start_events", new=_fake_stream_start_events),
            patch.object(server, "_create_forward_state", new=AsyncMock(return_value=fake_state)),
            patch("cli.connector.server.kill_process_group", new=AsyncMock()),
        ):
            await server._execute_start(body, response)

        assert tracking_gen.aclose_called, "event_gen.aclose() must be called on the success path"

    @pytest.mark.asyncio
    async def test_aclose_called_on_no_ready_path(self) -> None:
        """aclose() must be called when process exits without AF_READY."""
        server = _make_server()
        process = _fake_process()
        response = _make_response()

        tracking_gen: _TrackingAsyncGen = _TrackingAsyncGen(_gen_no_ready())

        body: dict[str, Any] = {
            "run_key": "run-no-ready",
            "ssh_target": "host",
            "sandbox_type": "docker",
            "start_cmd": "sandbox",
            "host_mounts": [],
            "work_dir": "",
        }

        async def _fake_stream_start_events(**kwargs: Any) -> tuple[asyncio.subprocess.Process, _TrackingAsyncGen]:
            return process, tracking_gen

        with (
            patch("cli.connector.server.stream_start_events", new=_fake_stream_start_events),
            patch("cli.connector.server.kill_process_group", new=AsyncMock()),
        ):
            await server._execute_start(body, response)

        assert tracking_gen.aclose_called, "event_gen.aclose() must be called when no AF_READY received"

    @pytest.mark.asyncio
    async def test_aclose_called_on_timeout_path(self) -> None:
        """aclose() must be called when _stream_and_collect times out."""
        server = _make_server()
        process = _fake_process()
        response = _make_response()

        async def _gen_infinite() -> AsyncGenerator[dict[str, Any], None]:
            while True:
                await asyncio.sleep(100)
                yield {"event": "log", "line": "never"}

        tracking_gen: _TrackingAsyncGen = _TrackingAsyncGen(_gen_infinite())

        body: dict[str, Any] = {
            "run_key": "run-timeout",
            "ssh_target": "host",
            "sandbox_type": "docker",
            "start_cmd": "sandbox",
            "host_mounts": [],
            "work_dir": "",
        }

        async def _fake_stream_start_events(**kwargs: Any) -> tuple[asyncio.subprocess.Process, _TrackingAsyncGen]:
            return process, tracking_gen

        with (
            patch("cli.connector.server.stream_start_events", new=_fake_stream_start_events),
            patch("cli.connector.server.kill_process_group", new=AsyncMock()),
            patch("cli.connector.server.SANDBOX_QUEUE_TIMEOUT_SEC", 0.01),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await server._execute_start(body, response)

        assert tracking_gen.aclose_called, "event_gen.aclose() must be called on the timeout path"
