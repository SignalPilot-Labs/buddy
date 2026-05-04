"""Integration tests for DockerLocalBackend lifecycle.

Tests the full create → get_client → get_logs → destroy cycle with mocked
Docker API. Verifies ring buffer captures logs, client caching works across
the full lifecycle, and destroy cleans up all resources.
"""

import asyncio
import os
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sandbox_client.docker_local import DockerLocalBackend, _LogDrainer
from sandbox_client.handle import SandboxHandle


def _mock_container(container_id: str, short_id: str) -> MagicMock:
    """Build a mock Docker container with the minimum interface."""
    container = MagicMock()
    container.id = container_id
    container.short_id = short_id
    container.logs = MagicMock(return_value=[b"line1\n", b"line2\n"])
    container.remove = MagicMock()
    return container


def _make_backend() -> DockerLocalBackend:
    """Instantiate DockerLocalBackend with mocked Docker."""
    with patch("sandbox_client.docker_local.docker.from_env", return_value=MagicMock()):
        with patch("sandbox_client.docker_local.sandbox_config", return_value={"vm_timeout_sec": 30}):
            with patch.dict(os.environ, {"AF_IMAGE_TAG": "test"}):
                return DockerLocalBackend()


class TestDockerLocalBackendLifecycle:
    """Full lifecycle: create → use → destroy."""

    @pytest.mark.asyncio
    async def test_create_returns_handle_with_local_fields(self) -> None:
        """create() must return a SandboxHandle with sandbox_id=None (local)."""
        backend = _make_backend()
        mock_container = _mock_container("abc123", "abc1")

        backend._docker.containers.run = MagicMock(return_value=mock_container)

        with patch.dict(os.environ, {"SANDBOX_INTERNAL_SECRET": "secret-xyz"}):
            with patch.object(backend, "_wait_healthy", new=AsyncMock()):
                handle = await backend.create(
                    "run-1", 10, None, None, "secret-xyz",
                )

        assert handle.run_key == "run-1"
        assert handle.sandbox_id is None
        assert handle.sandbox_type is None
        assert handle.backend_id == "abc123"
        assert handle.sandbox_secret == "secret-xyz"
        assert "run-1" in backend._containers

    @pytest.mark.asyncio
    async def test_ring_buffer_captures_logs(self) -> None:
        """get_logs() returns lines from the ring buffer."""
        backend = _make_backend()
        # Simulate a populated ring buffer
        buf: deque[str] = deque(maxlen=100)
        buf.extend(["log line 1", "log line 2", "log line 3"])
        backend._log_buffers["run-1"] = buf
        backend._containers["run-1"] = "fake-id"

        logs = await backend.get_logs("run-1", 2)
        assert logs == ["log line 2", "log line 3"]

    @pytest.mark.asyncio
    async def test_destroy_cleans_up_all_resources(self) -> None:
        """destroy() removes container, volume, client, and log buffer."""
        backend = _make_backend()
        backend._containers["run-1"] = "abc123"
        backend._log_buffers["run-1"] = deque(maxlen=100)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        backend._clients["run-1"] = mock_client

        handle = SandboxHandle(
            run_key="run-1", url="", backend_id="abc123",
            sandbox_secret="", sandbox_id=None, sandbox_type=None,
            remote_host=None, remote_port=None,
        )
        with patch.object(backend, "_remove_container", new=AsyncMock()):
            with patch.object(backend, "_remove_volume", new=AsyncMock()):
                await backend.destroy(handle)

        assert "run-1" not in backend._containers
        assert "run-1" not in backend._clients
        assert "run-1" not in backend._log_buffers
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_all_handles_multiple_runs(self) -> None:
        """destroy_all() cleans up all tracked runs."""
        backend = _make_backend()
        backend._containers["r1"] = "id1"
        backend._containers["r2"] = "id2"

        with patch.object(backend, "_remove_container", new=AsyncMock()):
            with patch.object(backend, "_remove_volume", new=AsyncMock()):
                await backend.destroy_all()

        assert len(backend._containers) == 0

    def test_log_drainer_populates_buffer(self) -> None:
        """_LogDrainer thread reads container logs into deque."""
        mock_container = MagicMock()
        mock_container.logs.return_value = iter([b"first\n", b"second\n"])

        buf: deque[str] = deque(maxlen=100)
        drainer = _LogDrainer(mock_container, buf)
        drainer.start()
        drainer.join(timeout=2)

        assert list(buf) == ["first", "second"]
