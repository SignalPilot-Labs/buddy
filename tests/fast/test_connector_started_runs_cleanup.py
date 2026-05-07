"""Regression test: ConnectorServer._destroy removes entries from _started_runs.

Bug: _destroy() popped entries from _states, _heartbeat_tasks, and _drain_tasks,
but never removed the corresponding entry from _started_runs. Over time this caused
unbounded memory growth as completed/destroyed runs accumulated in _started_runs.

Fix: After self._states.pop(run_key, None), also call self._started_runs.pop(run_key, None).
"""

from unittest.mock import MagicMock, patch

import pytest

from cli.connector.forward_state import ForwardState
from cli.connector.server import ConnectorServer

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


class TestStartedRunsCleanup:
    """Verify _destroy removes the entry from _started_runs to prevent memory leak."""

    @pytest.mark.asyncio
    async def test_started_runs_entry_removed_after_destroy(
        self, server: ConnectorServer
    ) -> None:
        """_started_runs must not contain the run_key after _destroy completes."""
        run_key = "run-abc"
        server._states[run_key] = _make_fake_state(run_key)
        server._started_runs[run_key] = ("user@hpc", "docker", "")

        with patch("cli.connector.server.kill_process_group", new=_noop_async):
            await server._destroy(run_key)

        assert run_key not in server._started_runs, (
            "_started_runs must not retain entry after _destroy"
        )

    @pytest.mark.asyncio
    async def test_started_runs_cleaned_for_slurm(
        self, server: ConnectorServer
    ) -> None:
        """_started_runs entry is removed for slurm sandbox type too."""
        run_key = "slurm-run-1"
        state = _make_fake_state(run_key)
        state.sandbox_type = "slurm"
        state.work_dir = ""  # no overlay cleanup path needed
        server._states[run_key] = state
        server._started_runs[run_key] = ("user@hpc", "slurm", "")

        with patch("cli.connector.server.kill_process_group", new=_noop_async):
            await server._destroy(run_key)

        assert run_key not in server._started_runs

    @pytest.mark.asyncio
    async def test_started_runs_other_entries_untouched(
        self, server: ConnectorServer
    ) -> None:
        """_destroy must only remove the specific run_key, not all of _started_runs."""
        run_key_a = "run-a"
        run_key_b = "run-b"
        server._states[run_key_a] = _make_fake_state(run_key_a)
        server._started_runs[run_key_a] = ("user@hpc", "docker", "")
        server._started_runs[run_key_b] = ("user@hpc", "docker", "")

        with patch("cli.connector.server.kill_process_group", new=_noop_async):
            await server._destroy(run_key_a)

        assert run_key_a not in server._started_runs, "Destroyed run must be removed"
        assert run_key_b in server._started_runs, "Other run must remain"

    @pytest.mark.asyncio
    async def test_destroy_unknown_key_does_not_affect_started_runs(
        self, server: ConnectorServer
    ) -> None:
        """_destroy with unknown run_key returns without touching _started_runs."""
        run_key_existing = "run-existing"
        server._started_runs[run_key_existing] = ("user@hpc", "docker", "")

        await server._destroy("nonexistent-key")

        # The existing entry must remain untouched
        assert run_key_existing in server._started_runs
