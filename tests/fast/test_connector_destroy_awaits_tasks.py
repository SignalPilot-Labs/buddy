"""Regression test: ConnectorServer._destroy awaits cancelled heartbeat and drain tasks.

Bug: _destroy() called task.cancel() on heartbeat and drain tasks but did not
await them, leaving orphan tasks that could log warnings, leak resources, or
prevent clean shutdown.

Fix: After each task.cancel(), the task is awaited with try/except CancelledError,
matching the pattern from DockerLocalBackend._destroy_by_key().
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from cli.connector.server import ConnectorServer
from cli.connector.forward_state import ForwardState

TEST_SECRET = "test-secret"


async def _noop_async(*args: object) -> None:
    """Async no-op used to stub out IO-heavy helpers."""


def _make_fake_state(run_key: str) -> MagicMock:
    """Build a MagicMock that quacks like ForwardState with no backend_id."""
    state = MagicMock(spec=ForwardState)
    state.run_key = run_key
    state.backend_id = None
    state.start_process = None
    state.tunnel_process = MagicMock()
    state.work_dir = ""
    state.sandbox_type = "docker"
    return state


@pytest.fixture
def server() -> ConnectorServer:
    """Create a ConnectorServer with mocked internals, no real aiohttp app."""
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


class TestConnectorDestroyAwaitsTasks:
    """Verify _destroy awaits cancelled tasks so no orphan tasks remain."""

    @pytest.mark.asyncio
    async def test_heartbeat_task_is_done_after_destroy(self, server: ConnectorServer) -> None:
        """Heartbeat task must be done (not pending) after _destroy completes."""

        async def _long_running() -> None:
            await asyncio.sleep(10)

        hb_task: asyncio.Task[None] = asyncio.create_task(_long_running())
        server._heartbeat_tasks["run-abc"] = hb_task
        server._states["run-abc"] = _make_fake_state("run-abc")

        with patch("cli.connector.server.kill_process_group", new=_noop_async):
            await server._destroy("run-abc")

        assert hb_task.done(), "Heartbeat task must be done after _destroy"

    @pytest.mark.asyncio
    async def test_drain_task_is_done_after_destroy(self, server: ConnectorServer) -> None:
        """Drain task must be done (not pending) after _destroy completes."""

        async def _long_running() -> None:
            await asyncio.sleep(10)

        drain_task: asyncio.Task[None] = asyncio.create_task(_long_running())
        server._drain_tasks["run-xyz"] = drain_task
        server._states["run-xyz"] = _make_fake_state("run-xyz")

        with patch("cli.connector.server.kill_process_group", new=_noop_async):
            await server._destroy("run-xyz")

        assert drain_task.done(), "Drain task must be done after _destroy"

    @pytest.mark.asyncio
    async def test_both_tasks_done_after_destroy(self, server: ConnectorServer) -> None:
        """Both heartbeat and drain tasks must be done after _destroy."""

        async def _long_running() -> None:
            await asyncio.sleep(10)

        hb_task: asyncio.Task[None] = asyncio.create_task(_long_running())
        drain_task: asyncio.Task[None] = asyncio.create_task(_long_running())

        server._heartbeat_tasks["run-both"] = hb_task
        server._drain_tasks["run-both"] = drain_task
        server._states["run-both"] = _make_fake_state("run-both")

        with patch("cli.connector.server.kill_process_group", new=_noop_async):
            await server._destroy("run-both")

        assert hb_task.done(), "Heartbeat task must be done"
        assert drain_task.done(), "Drain task must be done"

    @pytest.mark.asyncio
    async def test_destroy_no_op_for_unknown_run_key(self, server: ConnectorServer) -> None:
        """_destroy on an unknown run_key must return without raising."""
        await server._destroy("nonexistent-key")  # Must not raise
